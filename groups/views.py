from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from django.db import IntegrityError
from .models import Group
from progress.models import CourseEnrollment


class GroupInfoView(APIView):
    """Получить информацию о группе по токену (БЕЗ авторизации)"""
    permission_classes = [AllowAny]

    def get(self, request, token):
        # Находим группу по токену
        group = get_object_or_404(Group, referral_token=token, is_active=True)

        return Response({
            'group': {
                'name': group.name,
                'description': group.description,
                'course': {
                    'title': group.course.title,
                    'description': group.course.description,
                    'duration': group.course.duration,
                },
                'is_paid': group.is_paid,
                'deadline_days': group.deadline_days,
                'is_full': group.is_full(),
                'available_slots': str(group.get_available_slots()),
            }
        })


class JoinGroupByTokenView(APIView):
    """Присоединиться к группе по реферальному токену"""
    permission_classes = [IsAuthenticated]

    def post(self, request, token):
        # Находим группу по токену
        group = get_object_or_404(Group, referral_token=token, is_active=True)

        # Проверяем, что группа не заполнена
        if group.is_full():
            return Response(
                {'error': 'Группа заполнена'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Проверяем существующее зачисление на этот курс
        existing_enrollment = CourseEnrollment.objects.filter(
            user=request.user,
            course=group.course,
            is_active=True
        ).first()

        if existing_enrollment:
            # Случай 1: Студент уже в этой же группе
            if existing_enrollment.group and existing_enrollment.group.id == group.id:
                return Response(
                    {'error': f'Вы уже состоите в группе "{group.name}"'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Случай 2: Студент в другой группе (или group=None) → ПЕРЕВОДИМ
            old_group_name = existing_enrollment.group.name if existing_enrollment.group else "без группы"

            # Удаляем из старой группы (если была)
            if existing_enrollment.group:
                existing_enrollment.group.remove_student(request.user)

            # Добавляем в новую группу (дедлайн рассчитается заново)
            success, message = group.add_student(request.user, enrolled_via_referral=True)

            if not success:
                return Response(
                    {'error': message},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Обновляем зачисление
            existing_enrollment.group = group
            existing_enrollment.save()

            return Response({
                'success': True,
                'message': f'Вы переведены из "{old_group_name}" в группу "{group.name}". Ваш прогресс сохранен.',
                'enrollment': {
                    'course': group.course.title,
                    'group': group.name,
                    'old_group': old_group_name,
                    'payment_required': group.is_paid,
                    'deadline_days': group.deadline_days,
                    'progress_percentage': float(existing_enrollment.progress_percentage),
                }
            })

        # Случай 3: Новое зачисление на курс
        # Добавляем студента в группу
        success, message = group.add_student(request.user, enrolled_via_referral=True)

        if not success:
            return Response(
                {'error': message},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Создаем зачисление на курс (с защитой от race condition)
        try:
            enrollment = CourseEnrollment.objects.create(
                user=request.user,
                course=group.course,
                group=group,
                is_active=True
            )
        except IntegrityError:
            # Enrollment уже существует — получаем и обновляем
            enrollment = CourseEnrollment.objects.get(
                user=request.user,
                course=group.course
            )
            enrollment.group = group
            enrollment.is_active = True
            enrollment.save(update_fields=['group', 'is_active'])

        # Инициализируем прогресс для всех уроков
        from content.models import Lesson
        from progress.models import LessonProgress

        lessons = Lesson.objects.filter(module__course=group.course).order_by('module__order', 'order')

        for lesson in lessons:
            # Используем безопасный метод
            progress, created = LessonProgress.get_or_create_safe(
                user=request.user,
                lesson=lesson
            )
            # Рассчитываем доступность урока только для новых записей
            if created:
                progress.calculate_available_at()

        return Response({
            'success': True,
            'message': f'Вы успешно добавлены в группу "{group.name}"',
            'enrollment': {
                'course': group.course.title,
                'group': group.name,
                'payment_required': group.is_paid,
                'deadline_days': group.deadline_days,
            }
        }, status=status.HTTP_201_CREATED)