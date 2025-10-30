from typing import Optional
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone

from ..models import EmailLog
from .sendpulse import SendPulseService


class EmailService:
    """Высокоуровневый сервис для отправки email"""

    @staticmethod
    def _send_email(
            recipient: str,
            subject: str,
            template_name: str,
            context: dict,
            email_type: str,
            user=None
    ) -> EmailLog:
        """
        Универсальный метод отправки email

        Args:
            recipient: Email получателя
            subject: Тема письма
            template_name: Имя шаблона (например, 'emails/verification.html')
            context: Контекст для шаблона
            email_type: Тип письма из EmailLog.EMAIL_TYPES
            user: Объект пользователя (опционально)

        Returns:
            EmailLog: Объект лога отправки
        """
        # Создаем лог
        email_log = EmailLog.objects.create(
            user=user,
            recipient=recipient,
            email_type=email_type,
            subject=subject,
            status='pending'
        )

        try:
            # Добавляем общие переменные в контекст
            context.update({
                'site_name': settings.SENDPULSE_FROM_NAME,
                'frontend_url': settings.FRONTEND_URL,
                'current_year': timezone.now().year,
            })

            # Рендерим HTML из шаблона
            html_content = render_to_string(template_name, context)

            # Отправляем через SendPulse
            sendpulse = SendPulseService()
            result = sendpulse.send_email(
                to_email=recipient,
                subject=subject,
                html_content=html_content
            )

            # Обновляем лог
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
    def send_verification_email(cls, user, token: str) -> EmailLog:
        """Отправить письмо для подтверждения email"""
        verification_link = f"{settings.FRONTEND_URL}/set-password?token={token}"

        return cls._send_email(
            recipient=user.email,
            subject='Подтверждение регистрации на Aerialsolutions.kz',
            template_name='emails/verification.html',
            context={
                'user': user,
                'verification_link': verification_link,
            },
            email_type='email_verification',
            user=user
        )

    @classmethod
    def send_password_reset_email(cls, user, token: str) -> EmailLog:
        """Отправить письмо для сброса пароля"""
        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}"

        return cls._send_email(
            recipient=user.email,
            subject='Сброс пароля на Aerialsolutions.kz',
            template_name='emails/password_reset.html',
            context={
                'user': user,
                'reset_link': reset_link,
            },
            email_type='password_reset',
            user=user
        )