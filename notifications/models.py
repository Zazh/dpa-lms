from django.db import models
from django.conf import settings


class EmailLog(models.Model):
    """Лог отправленных email писем"""

    EMAIL_TYPES = [
        ('email_verification', 'Подтверждение email'),
        ('password_reset', 'Сброс пароля'),
        ('payment_success', 'Успешная оплата'),
        ('newsletter', 'Новостная рассылка'),
        ('activity_digest', 'Дайджест активности'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Ожидает отправки'),
        ('sent', 'Отправлено'),
        ('failed', 'Ошибка'),
    ]

    # Получатель
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='email_logs',
        verbose_name='Пользователь'
    )
    recipient = models.EmailField('Email получателя', db_index=True)

    # Информация о письме
    email_type = models.CharField('Тип письма', max_length=50, choices=EMAIL_TYPES, db_index=True)
    subject = models.CharField('Тема письма', max_length=255)

    # Статус
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    error_message = models.TextField('Сообщение об ошибке', blank=True)

    # Интеграция с SendPulse
    sendpulse_response = models.JSONField('Ответ SendPulse', null=True, blank=True)

    # Временные метки
    created_at = models.DateTimeField('Создано', auto_now_add=True, db_index=True)
    sent_at = models.DateTimeField('Отправлено', null=True, blank=True)

    class Meta:
        verbose_name = 'Лог отправки email'
        verbose_name_plural = 'Логи отправки email'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at', 'status']),
            models.Index(fields=['email_type', 'status']),
        ]

    def __str__(self):
        return f"{self.get_email_type_display()} → {self.recipient} ({self.get_status_display()})"