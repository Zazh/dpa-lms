import logging
from typing import Optional
from django.contrib.auth import get_user_model

from ..models import Notification, NotificationPreference
from .email_service import EmailService

logger = logging.getLogger(__name__)

User = get_user_model()


class NotificationService:
    """Сервис для управления уведомлениями"""

    @classmethod
    def _get_user_preferences(cls, user) -> NotificationPreference:
        """
        Получить настройки пользователя (или создать дефолтные)
        """
        preferences, created = NotificationPreference.objects.get_or_create(user=user)
        if created:
            logger.info(f"Созданы настройки уведомлений для {user.email}")
        return preferences


    @classmethod
    def notify_registration_completed(cls, user):
        """
        Уведомление: регистрация успешно завершена
        Вызывается после установки пароля
        """
        logger.info(f"Отправка уведомления о завершении регистрации для {user.email}")

        prefs = cls._get_user_preferences(user)

        # 1. In-app уведомление
        if prefs.registration_completed_in_app:
            Notification.objects.create(
                user=user,
                type='registration_completed',
                title='Регистрация успешно завершена!',
                message=f'Добро пожаловать, {user.first_name}! Ваш аккаунт активирован и готов к использованию.',
                link='/dashboard/'
            )
            logger.info(f"Создано in-app уведомление для {user.email}")

        # 2. Email уведомление
        if prefs.registration_completed_email:
            EmailService.send_registration_completed_email(user)
            logger.info(f"Отправлен email о завершении регистрации для {user.email}")


    @classmethod
    def notify_lesson_available(cls, user, lesson):
        """
        Уведомление: урок стал доступен
        Вызывается когда пользователь завершает предыдущий урок
        """
        logger.info(f"Отправка уведомления о доступном уроке для {user.email}: {lesson.title}")

        prefs = cls._get_user_preferences(user)

        # 1. In-app уведомление
        if prefs.lesson_available_in_app:
            Notification.objects.create(
                user=user,
                type='lesson_available',
                title=f'Урок "{lesson.title}" доступен',
                message=f'Вы можете приступить к изучению урока "{lesson.title}"',
                link=f'/lessons/{lesson.id}/'
            )
            logger.info(f"Создано in-app уведомление для {user.email}")

        # 2. Email уведомление
        if prefs.lesson_available_email:
            EmailService.send_lesson_available_email(user, lesson)
            logger.info(f"Отправлен email о доступном уроке для {user.email}")

    @classmethod
    def notify_homework_accepted(cls, user, assignment_submission):
        """
        Уведомление: домашнее задание принято (зачтено)
        Вызывается когда преподаватель зачитывает работу
        """
        logger.info(f"Отправка уведомления о принятом ДЗ для {user.email}")

        prefs = cls._get_user_preferences(user)
        assignment = assignment_submission.assignment

        # 1. In-app уведомление
        if prefs.homework_accepted_in_app:
            Notification.objects.create(
                user=user,
                type='homework_accepted',
                title=f'Домашнее задание принято!',
                message=f'Преподаватель принял ваше задание "{assignment.lesson.title}". Балл: {assignment_submission.score}/{assignment.max_score}',
                link=f'/assignments/submissions/{assignment_submission.id}/'
            )
            logger.info(f"Создано in-app уведомление о принятом ДЗ для {user.email}")

        # 2. Email уведомление
        if prefs.homework_accepted_email:
            EmailService.send_homework_accepted_email(user, assignment_submission)
            logger.info(f"Отправлен email о принятом ДЗ для {user.email}")

    @classmethod
    def notify_homework_needs_revision(cls, user, assignment_submission):
        """
        Уведомление: домашнее задание требует доработки
        Вызывается когда преподаватель отправляет работу на доработку
        """
        logger.info(f"Отправка уведомления о доработке ДЗ для {user.email}")

        prefs = cls._get_user_preferences(user)
        assignment = assignment_submission.assignment

        # 1. In-app уведомление
        if prefs.homework_needs_revision_in_app:
            Notification.objects.create(
                user=user,
                type='homework_needs_revision',
                title=f'Домашнее задание требует доработки',
                message=f'Преподаватель оставил комментарии к заданию "{assignment.lesson.title}". Пожалуйста, исправьте и сдайте повторно.',
                link=f'/assignments/submissions/{assignment_submission.id}/'
            )
            logger.info(f"Создано in-app уведомление о доработке ДЗ для {user.email}")

        # 2. Email уведомление
        if prefs.homework_needs_revision_email:
            EmailService.send_homework_needs_revision_email(user, assignment_submission)
            logger.info(f"Отправлен email о доработке ДЗ для {user.email}")