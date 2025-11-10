from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import Course, Lesson, VideoLesson, TextLesson
from .serializers import (
    CourseListSerializer,
    CourseDetailSerializer,
    VideoLessonDetailSerializer,
    TextLessonDetailSerializer,
    LessonMaterialSerializer
)
from progress.models import CourseEnrollment, LessonProgress, VideoProgress


class CourseListView(APIView):
    """
    GET /api/courses/
    Каталог курсов (вкладка "Все курсы")
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        courses = Course.objects.filter(is_active=True).order_by('-created_at')
        serializer = CourseListSerializer(courses, many=True, context={'request': request})
        return Response(serializer.data)


class CourseDetailView(APIView):
    """
    GET /api/courses/{id}/
    Детали курса (без прогресса)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        course = get_object_or_404(Course, pk=pk, is_active=True)
        serializer = CourseDetailSerializer(course, context={'request': request})
        return Response(serializer.data)


class LessonDetailView(APIView):
    """
    GET /api/lessons/{id}/
    Детали урока (контент + прогресс)

    Автозавершение текстовых уроков при первом открытии
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        lesson = get_object_or_404(Lesson, pk=pk)

        # Проверка 1: Зачислен ли пользователь на курс
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

        # Проверка 2: Есть ли доступ к курсу (активное членство в группе)
        if not enrollment.has_access():
            return Response(
                {'error': 'Доступ к курсу закрыт. Возможно истек дедлайн или вы удалены из группы.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Получаем или создаем прогресс урока
        lesson_progress, created = LessonProgress.objects.get_or_create(
            user=request.user,
            lesson=lesson,
            defaults={'is_completed': False}
        )

        # Если только создали - рассчитываем доступность
        if created:
            lesson_progress.calculate_available_at()

        # Проверка 3: Доступен ли урок
        if not lesson_progress.is_available():
            available_in = self._get_available_in(lesson_progress.available_at)
            return Response(
                {
                    'error': 'Урок недоступен',
                    'available_at': lesson_progress.available_at,
                    'available_in': available_in
                },
                status=status.HTTP_403_FORBIDDEN
            )

        # Подготовка базовых данных урока
        response_data = {
            'lesson': {
                'id': lesson.id,
                'title': lesson.title,
                'description': lesson.description,
                'type': lesson.lesson_type
            },
            'materials': LessonMaterialSerializer(lesson.materials.all(), many=True).data
        }

        # В зависимости от типа урока добавляем специфичные данные
        if lesson.lesson_type == 'video':
            response_data.update(self._get_video_lesson_data(lesson, request.user))

        elif lesson.lesson_type == 'text':
            response_data.update(self._get_text_lesson_data(lesson, lesson_progress))

        elif lesson.lesson_type == 'quiz':
            response_data.update(self._get_quiz_lesson_data(lesson, request.user))  # ← НОВОЕ

        elif lesson.lesson_type == 'assignment':
            response_data['assignment'] = {
                'message': 'Домашнее задание доступно. Перейдите к выполнению.'
            }

        return Response(response_data)

    def _get_video_lesson_data(self, lesson, user):
        """Данные для видео-урока"""
        video_lesson = get_object_or_404(VideoLesson, lesson=lesson)

        # Получаем или создаем прогресс видео
        video_progress, created = VideoProgress.objects.get_or_create(
            user=user,
            video_lesson=video_lesson
        )

        return {
            'video': VideoLessonDetailSerializer(video_lesson).data,
            'progress': {
                'is_completed': LessonProgress.objects.get(user=user, lesson=lesson).is_completed,
                'watch_percentage': float(video_progress.watch_percentage),
                'started_at': video_progress.started_at
            }
        }

    def _get_text_lesson_data(self, lesson, lesson_progress):
        """Данные для текстового урока"""
        text_lesson = get_object_or_404(TextLesson, lesson=lesson)

        # АВТОЗАВЕРШЕНИЕ при первом открытии
        if not lesson_progress.is_completed:
            lesson_progress.mark_completed()

        return {
            'text': TextLessonDetailSerializer(text_lesson).data,
            'progress': {
                'is_completed': True  # Всегда true после открытия
            }
        }

    def _get_quiz_lesson_data(self, lesson, user):
        """Данные для теста"""
        from quizzes.models import QuizLesson
        from quizzes.serializers import QuizLessonDetailSerializer

        quiz_lesson = get_object_or_404(QuizLesson, lesson=lesson)

        # Получаем прогресс урока
        lesson_progress = LessonProgress.objects.get(user=user, lesson=lesson)

        return {
            'quiz': QuizLessonDetailSerializer(
                quiz_lesson,
                context={'request': self.request}
            ).data,
            'progress': {
                'is_completed': lesson_progress.is_completed
            }
        }

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