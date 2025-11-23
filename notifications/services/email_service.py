from typing import Optional
from django.conf import settings
from django.utils import timezone
import logging

from ..models import EmailLog
from .sendpulse import SendPulseService

logger = logging.getLogger(__name__)


class EmailService:
    """Высокоуровневый сервис для отправки email"""

    @classmethod
    def send_verification_email(cls, user, token: str) -> EmailLog:
        """Отправить письмо для подтверждения email"""
        verification_link = f"{settings.FRONTEND_URL}/set-password?token={token}"

        # ПРОСТОЙ ТЕКСТ
        text_content = f"""
        Здравствуйте, {user.first_name}!

        Спасибо за регистрацию на платформе Aerialsolutions.kz

        Для завершения регистрации и установки пароля перейдите по ссылке:
        {verification_link}

        Ссылка действительна 24 часа.

        Если вы не регистрировались - проигнорируйте это письмо.

        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        С уважением,
        Команда Aerialsolutions.kz

        Контакты:
        Email: support@aerialsolutions.kz
        Сайт: https://aerialsolutions.kz

        Это автоматическое письмо, не отвечайте на него.
        Если у вас возникли вопросы, напишите на support@aerialsolutions.kz
            """

        email_log = EmailLog.objects.create(
            user=user,
            recipient=user.email,
            email_type='email_verification',
            subject='Подтверждение регистрации',
            status='pending'
        )

        try:
            logger.info(f"Sending email to {user.email}")
            logger.info(f"Link: {verification_link}")

            sendpulse = SendPulseService()
            result = sendpulse.send_email(
                to_email=user.email,
                subject='Подтверждение регистрации на aerialsolutions.kz',
                html_content=text_content
            )

            if result['success']:
                email_log.status = 'sent'
                email_log.sent_at = timezone.now()
                email_log.sendpulse_response = result.get('response')
            else:
                email_log.status = 'failed'
                email_log.error_message = result['message']

        except Exception as e:
            email_log.status = 'failed'
            email_log.error_message = str(e)
            logger.error(f"Error: {e}")

        email_log.save()
        return email_log

    @classmethod
    def send_password_reset_email(cls, user, token: str) -> EmailLog:
        """Отправить письмо для сброса пароля"""
        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}"

        # ПРОСТОЙ ТЕКСТ
        text_content = f"""
        Здравствуйте, {user.first_name}!

        Вы запросили сброс пароля на aerialsolutions.kz

        Для сброса пароля перейдите по ссылке:
        {reset_link}

        Ссылка действительна 1 час.

        Если вы не запрашивали сброс - проигнорируйте это письмо.

        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        С уважением,
        Команда Aerialsolutions.kz

        Контакты:
        Email: support@aerialsolutions.kz
        Сайт: https://aerialsolutions.kz

        Это автоматическое письмо, не отвечайте на него.
        Если у вас возникли вопросы, напишите на support@aerialsolutions.kz
            """

        email_log = EmailLog.objects.create(
            user=user,
            recipient=user.email,
            email_type='password_reset',
            subject='Сброс пароля',
            status='pending'
        )

        try:
            sendpulse = SendPulseService()
            result = sendpulse.send_email(
                to_email=user.email,
                subject='Сброс пароля на aerialsolutions.kz',
                html_content=text_content
            )

            if result['success']:
                email_log.status = 'sent'
                email_log.sent_at = timezone.now()
                email_log.sendpulse_response = result.get('response')
            else:
                email_log.status = 'failed'
                email_log.error_message = result['message']

        except Exception as e:
            email_log.status = 'failed'
            email_log.error_message = str(e)

        email_log.save()
        return email_log

    @classmethod
    def send_registration_completed_email(cls, user) -> EmailLog:
        """Отправить письмо об успешной регистрации"""

        text_content = f"""
        Здравствуйте, {user.first_name}!

        Регистрация на платформе Aerialsolutions.kz успешно завершена!

        Ваш аккаунт активирован и вы можете приступить к обучению.

        Войдите в личный кабинет:
        {settings.FRONTEND_URL}/login

        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        С уважением,
        Команда Aerialsolutions.kz

        Контакты:
        Email: support@aerialsolutions.kz
        Сайт: https://aerialsolutions.kz

        Это автоматическое письмо, не отвечайте на него.
        Если у вас возникли вопросы, напишите на support@aerialsolutions.kz
            """

        email_log = EmailLog.objects.create(
            user=user,
            recipient=user.email,
            email_type='email_verification',  # можно добавить новый тип 'registration_completed'
            subject='Регистрация завершена',
            status='pending'
        )

        try:
            sendpulse = SendPulseService()
            result = sendpulse.send_email(
                to_email=user.email,
                subject='Регистрация завершена на aerialsolutions.kz',
                html_content=text_content
            )

            if result['success']:
                email_log.status = 'sent'
                email_log.sent_at = timezone.now()
                email_log.sendpulse_response = result.get('response')
            else:
                email_log.status = 'failed'
                email_log.error_message = result['message']

        except Exception as e:
            email_log.status = 'failed'
            email_log.error_message = str(e)
            logger.error(f"Error: {e}")

        email_log.save()
        return email_log

    @classmethod
    def send_lesson_available_email(cls, user, lesson) -> EmailLog:
        """Отправить письмо о доступном уроке"""

        lesson_link = f"{settings.FRONTEND_URL}/lessons/{lesson.id}"

        text_content = f"""
        Здравствуйте, {user.first_name}!

        Новый урок доступен для изучения!

        Урок: {lesson.title}
        Курс: {lesson.module.course.title}
        Модуль: {lesson.module.title}

        Приступить к изучению:
        {lesson_link}

        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        С уважением,
        Команда Aerialsolutions.kz

        Контакты:
        Email: support@aerialsolutions.kz
        Сайт: https://aerialsolutions.kz

        Это автоматическое письмо, не отвечайте на него.
        Если у вас возникли вопросы, напишите на support@aerialsolutions.kz
            """

        email_log = EmailLog.objects.create(
            user=user,
            recipient=user.email,
            email_type='email_verification',  # можно добавить новый тип 'lesson_available'
            subject='Новый урок доступен',
            status='pending'
        )

        try:
            sendpulse = SendPulseService()
            result = sendpulse.send_email(
                to_email=user.email,
                subject=f'Новый урок доступен: {lesson.title}',
                html_content=text_content
            )

            if result['success']:
                email_log.status = 'sent'
                email_log.sent_at = timezone.now()
                email_log.sendpulse_response = result.get('response')
            else:
                email_log.status = 'failed'
                email_log.error_message = result['message']

        except Exception as e:
            email_log.status = 'failed'
            email_log.error_message = str(e)
            logger.error(f"Error: {e}")

        email_log.save()
        return email_log

    @classmethod
    def send_homework_accepted_email(cls, user, assignment_submission) -> EmailLog:
        """Отправить письмо о принятом ДЗ"""

        assignment = assignment_submission.assignment
        submission_link = f"{settings.FRONTEND_URL}/assignments/submissions/{assignment_submission.id}"

        text_content = f"""
        Здравствуйте, {user.first_name}!

        Ваше домашнее задание принято!

        Задание: {assignment.lesson.title}
        Курс: {assignment.lesson.module.course.title}
        Попытка №{assignment_submission.submission_number}

        Балл: {assignment_submission.score}/{assignment.max_score} ({assignment_submission.get_score_percentage()}%)

        Комментарий преподавателя:
        {assignment_submission.feedback if assignment_submission.feedback else 'Без комментариев'}

        Посмотреть детали:
        {submission_link}

        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        С уважением,
        Команда Aerialsolutions.kz

        Контакты:
        Email: support@aerialsolutions.kz
        Сайт: https://aerialsolutions.kz

        Это автоматическое письмо, не отвечайте на него.
        Если у вас возникли вопросы, напишите на support@aerialsolutions.kz
            """

        email_log = EmailLog.objects.create(
            user=user,
            recipient=user.email,
            email_type='email_verification',  # можно добавить новый тип
            subject='Домашнее задание принято',
            status='pending'
        )

        try:
            sendpulse = SendPulseService()
            result = sendpulse.send_email(
                to_email=user.email,
                subject=f'Домашнее задание принято: {assignment.lesson.title}',
                html_content=text_content
            )

            if result['success']:
                email_log.status = 'sent'
                email_log.sent_at = timezone.now()
                email_log.sendpulse_response = result.get('response')
            else:
                email_log.status = 'failed'
                email_log.error_message = result['message']

        except Exception as e:
            email_log.status = 'failed'
            email_log.error_message = str(e)
            logger.error(f"Error: {e}")

        email_log.save()
        return email_log

    @classmethod
    def send_homework_needs_revision_email(cls, user, assignment_submission) -> EmailLog:
        """Отправить письмо о необходимости доработки ДЗ"""

        assignment = assignment_submission.assignment
        submission_link = f"{settings.FRONTEND_URL}/assignments/submissions/{assignment_submission.id}"

        text_content = f"""
        Здравствуйте, {user.first_name}!

        Ваше домашнее задание требует доработки.

        Задание: {assignment.lesson.title}
        Курс: {assignment.lesson.module.course.title}
        Попытка №{assignment_submission.submission_number}

        Комментарий преподавателя:
        {assignment_submission.feedback if assignment_submission.feedback else 'Без комментариев'}

        Пожалуйста, исправьте работу и сдайте повторно.

        Посмотреть детали и комментарии:
        {submission_link}

        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        С уважением,
        Команда Aerialsolutions.kz

        Контакты:
        Email: support@aerialsolutions.kz
        Сайт: https://aerialsolutions.kz

        Это автоматическое письмо, не отвечайте на него.
        Если у вас возникли вопросы, напишите на support@aerialsolutions.kz
            """

        email_log = EmailLog.objects.create(
            user=user,
            recipient=user.email,
            email_type='email_verification',  # можно добавить новый тип
            subject='Домашнее задание требует доработки',
            status='pending'
        )

        try:
            sendpulse = SendPulseService()
            result = sendpulse.send_email(
                to_email=user.email,
                subject=f'Требуется доработка: {assignment.lesson.title}',
                html_content=text_content
            )

            if result['success']:
                email_log.status = 'sent'
                email_log.sent_at = timezone.now()
                email_log.sendpulse_response = result.get('response')
            else:
                email_log.status = 'failed'
                email_log.error_message = result['message']

        except Exception as e:
            email_log.status = 'failed'
            email_log.error_message = str(e)
            logger.error(f"Error: {e}")

        email_log.save()
        return email_log