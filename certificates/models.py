from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid


class CertificateTemplate(models.Model):
    """Шаблон сертификата для курса"""

    course = models.OneToOneField(
        'content.Course',
        on_delete=models.CASCADE,
        related_name='certificate_template',
        verbose_name='Курс'
    )

    # === НАЗВАНИЕ КУРСА ===
    full_course_title = models.CharField(
        'Полное название курса',
        max_length=500,
        help_text='Название для сертификата (может отличаться от названия на сайте)'
    )

    # === ТЕКСТ ДАТЫ ===
    issue_date_label = models.CharField(
        'Текст даты выдачи',
        max_length=100,
        default='Дата выдачи:',
        blank=True,
        help_text='Оставьте пустым, если дата не нужна'
    )

    # === ПЕЧАТЬ И ПОДПИСЬ (CSS классы) ===
    stamp_css_class = models.CharField(
        'CSS класс печати',
        max_length=50,
        default='stamp-img-1',
        help_text='Например: stamp-img-1, stamp-img-2'
    )

    signature_css_class = models.CharField(
        'CSS класс подписи',
        max_length=50,
        default='aft-img-1',
        help_text='Например: aft-img-1, aft-img-2'
    )

    # === ПОДПИСАНТ ===
    signer_name = models.CharField(
        'ФИО подписавшего',
        max_length=255,
        help_text='Например: Иванов И.И.'
    )

    signer_position = models.CharField(
        'Должность подписавшего',
        max_length=255,
        help_text='Например: Генеральный директор'
    )

    # === ТЕКСТЫ ===
    certificate_title = models.CharField(
        'Заголовок сертификата',
        max_length=100,
        default='СЕРТИФИКАТ',
        help_text='Для успешно завершивших'
    )

    attended_title = models.CharField(
        'Заголовок "Прослушал"',
        max_length=100,
        default='СПРАВКА',
        help_text='Для не прошедших курс'
    )

    completion_text = models.CharField(
        'Текст завершения',
        max_length=255,
        default='успешно завершил(а) курс',
        help_text='Для сертификата'
    )

    attended_text = models.CharField(
        'Текст прослушивания',
        max_length=255,
        default='прослушал(а) курс',
        help_text='Для справки о прослушивании'
    )

    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Шаблон сертификата'
        verbose_name_plural = 'Шаблоны сертификатов'

    def __str__(self):
        return f'Шаблон: {self.course.title}'


class Certificate(models.Model):
    """Сертификат"""

    # === ТИП СЕРТИФИКАТА ===
    CERTIFICATE_TYPE_CHOICES = [
        ('certificate', 'Сертификат'),
        ('attended', 'Прослушал'),
    ]

    # === ИСТОЧНИК ===
    SOURCE_CHOICES = [
        ('internal', 'Выдан системой'),
        ('external', 'Внешний'),
    ]

    # === СТАТУС ===
    STATUS_CHOICES = [
        ('pending', 'Генерируется'),
        ('ready', 'Готов'),
        ('error', 'Ошибка генерации'),
    ]

    # === ОСНОВНЫЕ ПОЛЯ ===
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

    certificate_type = models.CharField(
        'Тип документа',
        max_length=20,
        choices=CERTIFICATE_TYPE_CHOICES,
        default='certificate',
        db_index=True
    )

    # === СВЯЗИ ===
    user = models.ForeignKey(
        'account.User',
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

    # === ДАННЫЕ СЕРТИФИКАТА ===
    number = models.CharField(
        'Номер сертификата',
        max_length=50,
        unique=True,
        db_index=True
    )

    holder_name = models.CharField('ФИО владельца', max_length=255)
    course_title = models.CharField('Название курса', max_length=500)
    group_name = models.CharField('Название группы', max_length=255, blank=True)

    # === ДАННЫЕ ИЗ ШАБЛОНА (копируются при создании) ===
    document_title = models.CharField(
        'Заголовок документа',
        max_length=100,
        default='СЕРТИФИКАТ'
    )

    completion_text = models.CharField(
        'Текст завершения',
        max_length=255,
        default='успешно завершил(а) курс'
    )

    issue_date_label = models.CharField(
        'Текст даты выдачи',
        max_length=100,
        default='Дата выдачи:',
        blank=True
    )

    stamp_css_class = models.CharField(
        'CSS класс печати',
        max_length=50,
        default='stamp-img-1'
    )

    signature_css_class = models.CharField(
        'CSS класс подписи',
        max_length=50,
        default='aft-img-1'
    )

    signer_name = models.CharField(
        'ФИО подписавшего',
        max_length=255,
        blank=True
    )

    signer_position = models.CharField(
        'Должность подписавшего',
        max_length=255,
        blank=True
    )

    # === ФАЙЛЫ ===
    file_without_stamp = models.FileField(
        'Без печати',
        upload_to='certificates/%Y/%m/',
        null=True,
        blank=True
    )

    file_with_stamp = models.FileField(
        'С печатью',
        upload_to='certificates/%Y/%m/',
        null=True,
        blank=True
    )

    # === ДАТЫ ===
    issued_at = models.DateField('Дата выдачи', db_index=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    # === ОШИБКИ ===
    error_message = models.TextField('Сообщение об ошибке', blank=True)

    class Meta:
        verbose_name = 'Сертификат'
        verbose_name_plural = 'Сертификаты'
        ordering = ['-issued_at', '-created_at']
        indexes = [
            models.Index(fields=['number']),
            models.Index(fields=['source', 'status']),
            models.Index(fields=['-issued_at']),
            models.Index(fields=['certificate_type']),
        ]

    def __str__(self):
        type_label = 'Справка' if self.certificate_type == 'attended' else 'Сертификат'
        return f'{type_label} {self.number} - {self.holder_name}'

    @classmethod
    def generate_number(cls) -> str:
        """Генерация уникального номера сертификата"""
        year = timezone.now().year
        unique_id = str(uuid.uuid4())[:6].upper()
        return f"KZ{year}{unique_id}"