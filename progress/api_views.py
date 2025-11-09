from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import CourseEnrollment, LessonProgress, VideoProgress
from .serializers import MyCourseSerializer, CourseProgressSerializer
from content.models import Course, Lesson


class MyCoursesView(APIView):
    """
    GET /api/courses/my/
    Мои курсы (с прогрессом и доступом)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Получаем все зачисления пользователя
        enrollments = CourseEnrollment.objects.filter(
            user=request.user,
            is_active=True
        ).select_related('course', 'group').order_by('-enrolled_at')

        # Фильтруем только с активным доступом
        active_enrollments = [e for e in enrollments if e.has_access()]

        serializer = MyCourseSerializer(active_enrollments, many=True)
        return Response(serializer.data)


class CourseProgressView(APIView):
    """
    GET /api/courses/{id}/progress/
    Структура курса с прогрессом и доступностью уроков
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        course = get_object_or_404(Course, pk=pk, is_active=True)

        # Проверка зачисления
        try:
            enrollment = CourseEnrollment.objects.get(
                user=request.user,
                course=course
            )
        except CourseEnrollment.DoesNotExist:
            return Response(
                {'error': 'Вы не зачислены на этот курс'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Проверка доступа
        if not enrollment.has_access():
            return Response(
                {'error': 'Доступ к курсу закрыт. Возможно истек дедлайн или вы удалены из группы.'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = CourseProgressSerializer(enrollment)
        return Response(serializer.data)


class LessonCompleteView(APIView):
    """
    POST /api/lessons/{id}/complete/
    Завершить урок

    Для видео: вызывается автоматически при просмотре 90%
    Для текста: автоматически при открытии (не требуется вызов)
    Для тестов/заданий: вызывается после успешной сдачи
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        lesson = get_object_or_404(Lesson, pk=pk)

        try:
            enrollment = CourseEnrollment.objects.get(
                user=request.user,
                course=lesson.module.course
            )
        except CourseEnrollment.DoesNotExist:
            return Response(
                {'error': 'Вы не зачислены на этот курс'},
                status=status.HTTP_403_FORBIDDEN
            )

            # Проверка доступа
        if not enrollment.has_access():
            return Response(
                {'error': 'Доступ к курсу закрыт'},
                status=status.HTTP_403_FORBIDDEN
            )

            # Получаем прогресс урока
        try:
            lesson_progress = LessonProgress.objects.get(
                user=request.user,
                lesson=lesson
            )
        except LessonProgress.DoesNotExist:
            return Response(
                {'error': 'Урок не был начат'},
                status=status.HTTP_400_BAD_REQUEST
            )

            # Проверка доступности урока
        if not lesson_progress.is_available():
            return Response(
                {'error': 'Урок недоступен'},
                status=status.HTTP_403_FORBIDDEN
            )

            # Для видео: проверяем процент просмотра
        if lesson.lesson_type == 'video':
            try:
                video_progress = VideoProgress.objects.get(
                    user=request.user,
                    video_lesson__lesson=lesson
                )

                if not video_progress.is_mostly_watched():
                    return Response(
                        {
                            'error': 'Необходимо просмотреть минимум 90% видео',
                            'current_percentage': float(video_progress.watch_percentage)
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except VideoProgress.DoesNotExist:
                return Response(
                    {'error': 'Видео не было просмотрено'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Завершаем урок (если еще не завершен)
        if not lesson_progress.is_completed:
            lesson_progress.mark_completed()
            # mark_completed() уже пересчитывает прогресс курса

            # Обновляем enrollment из БД (т.к. mark_completed изменил его)
        enrollment.refresh_from_db()

        # Получаем следующий урок
        next_lesson = self._get_next_lesson(lesson)
        next_lesson_data = None

        if next_lesson:
            next_progress, created = LessonProgress.objects.get_or_create(
                user=request.user,
                lesson=next_lesson,
                defaults={'is_completed': False}
            )

            if created:
                next_progress.calculate_available_at()

            next_lesson_data = {
                'id': next_lesson.id,
                'title': next_lesson.title,
                'type': next_lesson.lesson_type,
                'is_available': next_progress.is_available(),
                'available_at': next_progress.available_at,
                'available_in': self._get_available_in(next_progress.available_at)
            }

        # Подсчитываем общее количество уроков
        total_lessons = Lesson.objects.filter(module__course=enrollment.course).count()

        return Response({
            'success': True,
            'message': 'Урок завершен!',

            # РАСШИРЕННЫЙ ОТВЕТ: Прогресс курса
            'course_progress': {
                'percentage': float(enrollment.progress_percentage),
                'completed_lessons': enrollment.completed_lessons_count,
                'total_lessons': total_lessons
            },

            # Следующий урок
            'next_lesson': next_lesson_data
        })

    def _get_next_lesson(self, current_lesson):
        """Получить следующий урок в курсе"""
        # Пытаемся найти следующий урок в том же модуле
        next_in_module = Lesson.objects.filter(
            module=current_lesson.module,
            order__gt=current_lesson.order
        ).order_by('order').first()

        if next_in_module:
            return next_in_module

        # Если нет - ищем в следующем модуле
        from content.models import Module
        next_module = Module.objects.filter(
            course=current_lesson.module.course,
            order__gt=current_lesson.module.order
        ).order_by('order').first()

        if next_module:
            return Lesson.objects.filter(module=next_module).order_by('order').first()

        return None

    def _get_available_in(self, available_at):
        """Человекочитаемое время до доступности"""
        if not available_at:
            return None

        from django.utils import timezone
        delta = available_at - timezone.now()

        if delta.total_seconds() < 0:
            return "доступен сейчас"

        hours = int(delta.total_seconds() // 3600)
        minutes = int((delta.total_seconds() % 3600) // 60)

        if hours > 0 and minutes > 0:
            return f"через {hours} ч. {minutes} мин."
        elif hours > 0:
            return f"через {hours} ч."
        else:
            return f"через {minutes} мин."


class VideoProgressUpdateView(APIView):
    """
    POST /api/lessons/{id}/video-progress/
    Обновить прогресс просмотра видео

    Body: { "percentage": 45.5 }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        lesson = get_object_or_404(Lesson, pk=pk, lesson_type='video')

        # Проверка зачисления
        try:
            enrollment = CourseEnrollment.objects.get(
                user=request.user,
                course=lesson.module.course
            )
        except CourseEnrollment.DoesNotExist:
            return Response(
                {'error': 'Вы не зачислены на этот курс'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Проверка доступа
        if not enrollment.has_access():
            return Response(
                {'error': 'Доступ к курсу закрыт'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Получаем процент из запроса
        percentage = request.data.get('percentage')

        if percentage is None:
            return Response(
                {'error': 'Не передан параметр percentage'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            percentage = float(percentage)
            if percentage < 0 or percentage > 100:
                raise ValueError
        except (ValueError, TypeError):
            return Response(
                {'error': 'percentage должен быть числом от 0 до 100'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Получаем прогресс видео
        from content.models import VideoLesson
        video_lesson = get_object_or_404(VideoLesson, lesson=lesson)

        video_progress, created = VideoProgress.objects.get_or_create(
            user=request.user,
            video_lesson=video_lesson
        )

        # Обновляем прогресс
        video_progress.update_progress(percentage)

        return Response({
            'success': True,
            'watch_percentage': float(video_progress.watch_percentage),
            'is_mostly_watched': video_progress.is_mostly_watched()
        })