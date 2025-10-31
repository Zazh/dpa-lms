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