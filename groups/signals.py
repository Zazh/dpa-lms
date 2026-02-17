import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import GroupMembership

logger = logging.getLogger(__name__)


@receiver(post_save, sender=GroupMembership)
def auto_enroll_on_membership_create(sender, instance, created, **kwargs):
    """
    При создании активного GroupMembership автоматически:
    1. Создать/обновить CourseEnrollment
    2. Инициализировать LessonProgress для всех уроков курса
    """
    if not created or not instance.is_active:
        return

    from django.db import IntegrityError
    from content.models import Lesson
    from progress.models import CourseEnrollment, LessonProgress

    user = instance.user
    group = instance.group
    course = group.course

    # 1. Создаём или обновляем CourseEnrollment
    try:
        enrollment = CourseEnrollment.objects.create(
            user=user,
            course=course,
            group=group,
            is_active=True,
        )
        logger.info(
            f"Создано зачисление: {user.email} → {course.title} ({group.name})"
        )
    except IntegrityError:
        enrollment = CourseEnrollment.objects.get(user=user, course=course)
        enrollment.group = group
        enrollment.is_active = True
        enrollment.save(update_fields=['group', 'is_active'])
        logger.info(
            f"Обновлено зачисление: {user.email} → {course.title} ({group.name})"
        )

    # 2. Инициализируем LessonProgress
    lessons = Lesson.objects.filter(
        module__course=course
    ).order_by('module__order', 'order')

    for lesson in lessons:
        progress, lp_created = LessonProgress.get_or_create_safe(
            user=user, lesson=lesson
        )
        if lp_created:
            progress.calculate_available_at()

    logger.info(
        f"Инициализирован прогресс: {user.email}, "
        f"{lessons.count()} уроков курса «{course.title}»"
    )
