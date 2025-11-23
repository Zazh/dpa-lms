from django.db import models
from django.conf import settings
from django.utils import timezone


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


class Notification(models.Model):
    """In-app уведомления для личного кабинета"""

    NOTIFICATION_TYPES = [
        ('registration_completed', 'Регистрация завершена'),
        ('lesson_available', 'Урок доступен'),
        ('homework_accepted', 'Домашнее задание принято'),
        ('homework_needs_revision', 'Домашнее задание требует доработки'),
        ('course_enrolled', 'Зачисление на курс'),
        ('course_completed', 'Курс завершен'),
        ('promotion', 'Акция'),
        ('support_reply', 'Ответ поддержки'),
        ('bulk_notification', 'Массовая рассылка'),
        ('system', 'Системное уведомление'),
    ]

    # Получатель
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name='Пользователь'
    )

    # Тип и содержание
    type = models.CharField(
        'Тип уведомления',
        max_length=50,
        choices=NOTIFICATION_TYPES,
        db_index=True
    )
    title = models.CharField('Заголовок', max_length=255)
    message = models.TextField('Сообщение')
    link = models.CharField('Ссылка', max_length=500, blank=True)

    # Временная метка
    created_at = models.DateTimeField('Создано', auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Уведомление'
        verbose_name_plural = 'Уведомления'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['type', '-created_at']),
        ]

    def __str__(self):
        return f"{self.title} → {self.user.email}"

class NotificationPreference(models.Model):
    """Настройки уведомлений пользователя"""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preferences',
        verbose_name='Пользователь'
    )

    # === Регистрация завершена === ← ДОБАВИТЬ
    registration_completed_email = models.BooleanField(
        'Email: регистрация завершена',
        default=True
    )
    registration_completed_in_app = models.BooleanField(
        'In-app: регистрация завершена',
        default=True
    )

    # === Урок доступен ===
    lesson_available_email = models.BooleanField(
        'Email: урок доступен',
        default=True
    )
    lesson_available_push = models.BooleanField(
        'Push: урок доступен',
        default=True
    )
    lesson_available_in_app = models.BooleanField(
        'In-app: урок доступен',
        default=True
    )

    # === Домашнее задание принято ===
    homework_accepted_email = models.BooleanField(
        'Email: ДЗ принято',
        default=True
    )
    homework_accepted_push = models.BooleanField(
        'Push: ДЗ принято',
        default=True
    )
    homework_accepted_in_app = models.BooleanField(
        'In-app: ДЗ принято',
        default=True
    )

    # === Домашнее задание требует доработки ===
    homework_needs_revision_email = models.BooleanField(
        'Email: ДЗ требует доработки',
        default=True
    )
    homework_needs_revision_push = models.BooleanField(
        'Push: ДЗ требует доработки',
        default=True
    )
    homework_needs_revision_in_app = models.BooleanField(
        'In-app: ДЗ требует доработки',
        default=True
    )

    # === Курс завершен ===
    course_completed_email = models.BooleanField(
        'Email: курс завершен',
        default=True
    )
    course_completed_push = models.BooleanField(
        'Push: курс завершен',
        default=True
    )
    course_completed_in_app = models.BooleanField(
        'In-app: курс завершен',
        default=True
    )

    # === Акции и промо ===
    promotion_email = models.BooleanField(
        'Email: акции',
        default=False  # по умолчанию выключено
    )
    promotion_push = models.BooleanField(
        'Push: акции',
        default=False
    )
    promotion_in_app = models.BooleanField(
        'In-app: акции',
        default=True
    )

    # === Массовые рассылки ===
    bulk_notifications_email = models.BooleanField(
        'Email: массовые рассылки',
        default=True
    )
    bulk_notifications_push = models.BooleanField(
        'Push: массовые рассылки',
        default=True
    )
    bulk_notifications_in_app = models.BooleanField(
        'In-app: массовые рассылки',
        default=True
    )

    # === Поддержка ===
    support_reply_email = models.BooleanField(
        'Email: ответ поддержки',
        default=True
    )
    support_reply_push = models.BooleanField(
        'Push: ответ поддержки',
        default=True
    )
    support_reply_in_app = models.BooleanField(
        'In-app: ответ поддержки',
        default=True
    )

    # === Системные уведомления (всегда включены) ===
    system_email = models.BooleanField(
        'Email: системные',
        default=True
    )
    system_in_app = models.BooleanField(
        'In-app: системные',
        default=True
    )

    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Настройки уведомлений'
        verbose_name_plural = 'Настройки уведомлений'

    def __str__(self):
        return f"Настройки уведомлений: {self.user.email}"