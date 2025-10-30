from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from .models import Course, Lesson, CourseEnrollment, LessonProgress
from .serializers import (
    CourseListSerializer,
    CourseDetailSerializer,
    LessonSerializer,
    LessonProgressSerializer
)


class MyCourseListView(APIView):
    """Список курсов, на которые записан пользователь"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Получаем ID курсов, на которые записан пользователь
        enrolled_course_ids = CourseEnrollment.objects.filter(
            user=request.user
        ).values_list('course_id', flat=True)

        # Получаем активные курсы
        courses = Course.objects.filter(
            id__in=enrolled_course_ids,
            is_active=True
        )

        serializer = CourseListSerializer(
            courses,
            many=True,
            context={'request': request}
        )

        return Response(serializer.data)


class CourseDetailView(APIView):
    """Детальная информация о курсе"""
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        course = get_object_or_404(Course, id=course_id, is_active=True)

        # Проверяем, записан ли пользователь на курс
        enrollment = CourseEnrollment.objects.filter(
            user=request.user,
            course=course
        ).first()

        if not enrollment:
            return Response(
                {'error': 'У вас нет доступа к этому курсу'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = CourseDetailSerializer(
            course,
            context={'request': request}
        )

        return Response(serializer.data)


class LessonDetailView(APIView):
    """Детальная информация об уроке"""
    permission_classes = [IsAuthenticated]

    def get(self, request, lesson_id):
        lesson = get_object_or_404(
            Lesson.objects.prefetch_related('materials'),
            id=lesson_id,
            is_active=True
        )

        # Проверяем, записан ли пользователь на курс
        enrollment = CourseEnrollment.objects.filter(
            user=request.user,
            course=lesson.course
        ).first()

        if not enrollment:
            return Response(
                {'error': 'У вас нет доступа к этому уроку'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Проверяем доступность урока
        if lesson.requires_previous_completion:
            previous_lesson = lesson.get_previous_lesson()
            if previous_lesson:
                previous_completed = LessonProgress.objects.filter(
                    user=request.user,
                    lesson=previous_lesson,
                    is_completed=True
                ).exists()

                if not previous_completed:
                    return Response(
                        {
                            'error': 'Для доступа к этому уроку необходимо завершить предыдущий урок',
                            'previous_lesson': previous_lesson.title
                        },
                        status=status.HTTP_403_FORBIDDEN
                    )

        # Создаем или получаем прогресс по уроку
        progress, created = LessonProgress.objects.get_or_create(
            user=request.user,
            lesson=lesson
        )

        serializer = LessonSerializer(lesson, context={'request': request})

        return Response(serializer.data)


class CompleteLessonView(APIView):
    """Отметить урок как завершенный"""
    permission_classes = [IsAuthenticated]

    def post(self, request, lesson_id):
        lesson = get_object_or_404(Lesson, id=lesson_id, is_active=True)

        # Проверяем, записан ли пользователь на курс
        enrollment = CourseEnrollment.objects.filter(
            user=request.user,
            course=lesson.course
        ).first()

        if not enrollment:
            return Response(
                {'error': 'У вас нет доступа к этому уроку'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Проверяем доступность урока
        if lesson.requires_previous_completion:
            previous_lesson = lesson.get_previous_lesson()
            if previous_lesson:
                previous_completed = LessonProgress.objects.filter(
                    user=request.user,
                    lesson=previous_lesson,
                    is_completed=True
                ).exists()

                if not previous_completed:
                    return Response(
                        {
                            'error': 'Для завершения этого урока необходимо завершить предыдущий урок',
                            'previous_lesson': previous_lesson.title
                        },
                        status=status.HTTP_403_FORBIDDEN
                    )

        # Создаем или обновляем прогресс
        progress, created = LessonProgress.objects.get_or_create(
            user=request.user,
            lesson=lesson
        )

        if not progress.is_completed:
            progress.is_completed = True
            progress.save()
            message = 'Урок успешно завершен'
        else:
            message = 'Урок уже был завершен ранее'

        # Получаем обновленный прогресс по курсу
        course_progress = enrollment.get_progress_percentage()

        serializer = LessonProgressSerializer(progress)

        return Response({
            'message': message,
            'progress': serializer.data,
            'course_progress_percentage': course_progress
        })


class MyProgressView(APIView):
    """Общий прогресс пользователя по всем курсам"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        enrollments = CourseEnrollment.objects.filter(
            user=request.user
        ).select_related('course')

        progress_data = []
        for enrollment in enrollments:
            total_lessons = enrollment.course.get_total_lessons()
            completed_lessons = LessonProgress.objects.filter(
                user=request.user,
                lesson__course=enrollment.course,
                is_completed=True
            ).count()

            progress_data.append({
                'course_id': enrollment.course.id,
                'course_title': enrollment.course.title,
                'total_lessons': total_lessons,
                'completed_lessons': completed_lessons,
                'progress_percentage': enrollment.get_progress_percentage(),
                'enrolled_at': enrollment.enrolled_at
            })

        return Response(progress_data)