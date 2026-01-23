from django.db import models
from django.conf import settings


class Certificate(models.Model):
    """Сертификат (внутренний или внешний)"""

    SOURCE_CHOICES = [
        ('internal', 'Выдан системой'),
        ('external', 'Внешний'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Генерируется'),
        ('ready', 'Готов'),
        ('error', 'Ошибка генерации'),
    ]

    # Источник
    source = models.CharField(
        'Источник',
        max_length=20,
        choices=SOURCE_CHOICES,
        default='internal',
        db_index=True
    )

    status = models.CharField(
        'Статус',
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True
    )

    # Связи (опциональные — для внешних могут быть NULL)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='certificates',
        verbose_name='Пользователь'
    )

    graduate = models.OneToOneField(
        'graduates.Graduate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='certificate',
        verbose_name='Выпуск'
    )

    # Данные сертификата
    number = models.CharField(
        'Номер сертификата',
        max_length=50,
        unique=True,
        db_index=True
    )

    holder_name = models.CharField(
        'ФИО владельца',
        max_length=255
    )

    course_title = models.CharField(
        'Название курса',
        max_length=255
    )

    group_name = models.CharField(
        'Название группы',
        max_length=255,
        blank=True
    )

    # Файлы
    file_without_stamp = models.FileField(
        'Без печати',
        upload_to='certificates/%Y/%m/',
        blank=True,
        null=True
    )

    file_with_stamp = models.FileField(
        'С печатью',
        upload_to='certificates/%Y/%m/',
        blank=True,
        null=True
    )

    # Даты
    issued_at = models.DateField(
        'Дата выдачи',
        db_index=True
    )

    created_at = models.DateTimeField(
        'Создан',
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        'Обновлён',
        auto_now=True
    )

    # Ошибка генерации (если есть)
    error_message = models.TextField(
        'Сообщение об ошибке',
        blank=True
    )

    class Meta:
        verbose_name = 'Сертификат'
        verbose_name_plural = 'Сертификаты'
        ordering = ['-issued_at', '-created_at']
        indexes = [
            models.Index(fields=['number']),
            models.Index(fields=['source', 'status']),
            models.Index(fields=['-issued_at']),
        ]

    def __str__(self):
        return f"{self.number} — {self.holder_name}"

    @classmethod
    def generate_number(cls):
        """Генерация уникального номера сертификата"""
        import uuid
        from django.utils import timezone

        year = timezone.now().year
        unique_id = str(uuid.uuid4())[:6].upper()
        return f"KZ{year}{unique_id}"