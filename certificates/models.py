import re
import uuid

from django.db import models
from django.utils import timezone

# === ТРАНСЛИТЕРАЦИЯ ===
TRANSLIT_MAP = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    # Казахские буквы
    'ә': 'a', 'ғ': 'g', 'қ': 'q', 'ң': 'n', 'ө': 'o', 'ұ': 'u', 'ү': 'u',
    'һ': 'h', 'і': 'i',
}


def transliterate(text: str) -> str:
    """Транслитерация кириллицы в латиницу"""
    result = []
    for char in text.lower():
        if char in TRANSLIT_MAP:
            result.append(TRANSLIT_MAP[char])
        elif char.isalnum() or char in ' -_':
            result.append(char)
    return ''.join(result)


def make_slug(text: str, max_length: int = 50) -> str:
    """Создаёт slug из текста с транслитерацией"""
    # Транслитерация
    text = transliterate(text)
    # Заменяем пробелы и спецсимволы на дефисы
    text = re.sub(r'[^a-z0-9]+', '-', text)
    # Убираем дефисы в начале и конце
    text = text.strip('-')
    # Ограничиваем длину
    return text[:max_length]


def certificate_upload_path(instance, filename: str) -> str:
    """
    Генерирует путь для сертификата.

    Структура: certificates/{year}/{course-slug}/{month}/{iin}_{filename}
    Пример: certificates/2025/operator-bpla/01/123456789012_cert_KZ2025A1B2C3.pdf
    """
    from django.utils import timezone

    now = timezone.now()
    year = now.strftime('%Y')
    month = now.strftime('%m')

    # Slug курса
    course_slug = make_slug(instance.course_title) or 'unknown-course'

    # ИИН пользователя (добавляем в имя файла)
    if instance.user and instance.user.iin:
        iin = instance.user.iin
        filename = f"{iin}_{filename}"

    return f'certificates/{year}/{course_slug}/{month}/{filename}'


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

    course = models.ForeignKey(
        'content.Course',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='certificates',
        verbose_name='Курс'
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
        upload_to=certificate_upload_path,
        null=True,
        blank=True
    )

    file_with_stamp = models.FileField(
        'С печатью',
        upload_to=certificate_upload_path,
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
        constraints = [
            # Один сертификат на пользователя + курс + тип
            models.UniqueConstraint(
                fields=['user', 'course', 'certificate_type'],
                name='unique_user_course_certificate_type',
                condition=models.Q(user__isnull=False, course__isnull=False)
            ),
        ]
        indexes = [
            models.Index(fields=['number']),
            models.Index(fields=['source', 'status']),
            models.Index(fields=['-issued_at']),
            models.Index(fields=['certificate_type']),
            models.Index(fields=['user', 'course']),
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