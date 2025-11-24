from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from PIL import Image
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile
import sys

class Course(models.Model):
    """Курс обучения"""

    title = models.CharField('Название курса', max_length=255)
    label = models.CharField('Метка курса', max_length=100, blank=True, help_text='Например: "Базовый курс"')
    duration = models.CharField('Длительность', max_length=100, blank=True, help_text='Например: "3 месяца"')
    description = models.TextField('Описание курса', blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_courses',
        verbose_name='Создал'
    )

    is_active = models.BooleanField('Активен', default=True, db_index=True)

    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлен', auto_now=True)

    class Meta:
        verbose_name = 'Курс'
        verbose_name_plural = 'Курсы'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_active', '-created_at']),
        ]

    def __str__(self):
        return self.title

    def get_enrolled_students_count(self):
        """Получить количество записанных студентов"""
        # TODO: Будет работать после создания приложения progress
        return 0

        # # Будет работать после создания приложения progress
        # if hasattr(self, 'enrollments'):
        #     return self.enrollments.filter(is_active=True).count()
        # return 0

    def get_modules_count(self):
        """Количество модулей в курсе"""
        return self.modules.count()

    def get_lessons_count(self):
        """Общее количество уроков в курсе"""
        return sum(module.lessons.count() for module in self.modules.all())


class Module(models.Model):
    """Модуль курса"""

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='modules',
        verbose_name='Курс'
    )

    title = models.CharField('Название модуля', max_length=255)
    description = models.TextField('Описание модуля', blank=True)

    order = models.PositiveIntegerField('Порядок', default=0, db_index=True)
    requires_previous_module = models.BooleanField(
        'Требует завершения предыдущего модуля',
        default=True,
        help_text='⚠️ НЕ ИСПОЛЬЗУЕТСЯ. Логика доступности работает на уровне уроков.'
    )

    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлен', auto_now=True)

    class Meta:
        verbose_name = 'Модуль'
        verbose_name_plural = 'Модули'
        ordering = ['course', 'order']
        unique_together = ['course', 'order']
        indexes = [
            models.Index(fields=['course', 'order']),
        ]

    def __str__(self):
        return f"{self.course.title} - {self.title}"

    def get_lessons_count(self):
        """Количество уроков в модуле"""
        return self.lessons.count()

    def get_previous_module(self):
        """Получить предыдущий модуль"""
        return Module.objects.filter(
            course=self.course,
            order__lt=self.order
        ).order_by('-order').first()


class Lesson(models.Model):
    """Базовая модель урока (полиморфная)"""

    LESSON_TYPES = [
        ('video', '📹 Видео'),
        ('text', '📄 Текст'),
        ('quiz', '❓ Тест'),
        ('assignment', '📝 Домашнее задание'),
    ]

    module = models.ForeignKey(
        Module,
        on_delete=models.CASCADE,
        related_name='lessons',
        verbose_name='Модуль'
    )

    lesson_type = models.CharField(
        'Тип урока',
        max_length=20,
        choices=LESSON_TYPES,
        db_index=True
    )

    title = models.CharField('Название урока', max_length=255)
    description = models.TextField('Описание урока', blank=True)

    order = models.PositiveIntegerField('Порядок', default=0, db_index=True)

    access_delay_hours = models.PositiveIntegerField(
        'Задержка доступа (часы)',
        default=0,
        help_text='Через сколько часов после предыдущего урока откроется этот'
    )

    requires_previous_completion = models.BooleanField(
        'Требует завершения предыдущего урока',
        default=True
    )

    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлен', auto_now=True)

    class Meta:
        verbose_name = 'Урок'
        verbose_name_plural = 'Уроки'
        ordering = ['module', 'order']
        unique_together = ['module', 'order']
        indexes = [
            models.Index(fields=['module', 'order']),
            models.Index(fields=['lesson_type']),
        ]

    def __str__(self):
        return f"{self.get_lesson_type_display()} - {self.title}"

    def get_type_instance(self):
        """Получить экземпляр конкретного типа урока"""
        if self.lesson_type == 'video' and hasattr(self, 'videolesson'):
            return self.videolesson
        elif self.lesson_type == 'text' and hasattr(self, 'textlesson'):
            return self.textlesson
        elif self.lesson_type == 'quiz' and hasattr(self, 'quizlesson'):
            return self.quizlesson
        elif self.lesson_type == 'assignment' and hasattr(self, 'assignmentlesson'):
            return self.assignmentlesson
        return None

    def is_available_for_user(self, user):
        """Проверить доступность урока для пользователя"""
        # TODO: Метод заработает после создания приложения progress
        # Временно всегда возвращаем True
        return True

        # # Логика будет работать после создания приложения progress
        # from progress.models import LessonProgress
        #
        # # Если не требует завершения предыдущего урока
        # if not self.requires_previous_completion:
        #     return True
        #
        # # Получаем предыдущий урок
        # previous_lesson = self.get_previous_lesson()
        # if not previous_lesson:
        #     return True  # Первый урок всегда доступен
        #
        # # Проверяем завершение предыдущего урока
        # try:
        #     previous_progress = LessonProgress.objects.get(
        #         user=user,
        #         lesson=previous_lesson
        #     )
        #     if not previous_progress.is_completed:
        #         return False
        #
        #     # Проверяем задержку доступа
        #     if self.access_delay_hours > 0:
        #         time_since_completion = timezone.now() - previous_progress.completed_at
        #         required_delay = timezone.timedelta(hours=self.access_delay_hours)
        #         return time_since_completion >= required_delay
        #
        #     return True
        # except LessonProgress.DoesNotExist:
        #     return False

    def get_previous_lesson(self):
        """Получить предыдущий урок в курсе (учитывает модули)"""

        # 1. Ищем в том же модуле
        previous_in_module = Lesson.objects.filter(
            module=self.module,
            order__lt=self.order
        ).order_by('-order').first()

        if previous_in_module:
            return previous_in_module

        # 2. Ищем предыдущий модуль
        previous_module = Module.objects.filter(
            course=self.module.course,
            order__lt=self.module.order
        ).order_by('-order').first()

        if not previous_module:
            # Это первый урок курса
            return None

        # 3. Возвращаем последний урок предыдущего модуля
        return Lesson.objects.filter(
            module=previous_module
        ).order_by('-order').first()


    def get_next_lesson(self):
        """Получить следующий урок в курсе (учитывает модули)"""

        # 1. Ищем в том же модуле
        next_in_module = Lesson.objects.filter(
            module=self.module,
            order__gt=self.order
        ).order_by('order').first()

        if next_in_module:
            return next_in_module

        # 2. Ищем следующий модуль
        next_module = Module.objects.filter(
            course=self.module.course,
            order__gt=self.module.order
        ).order_by('order').first()

        if not next_module:
            # Это последний урок курса
            return None

        # 3. Возвращаем первый урок следующего модуля
        return Lesson.objects.filter(
            module=next_module
        ).order_by('order').first()

    def get_materials_count(self):
        """Количество материалов к уроку"""
        return self.materials.count()


class VideoLesson(models.Model):
    """Видео-урок (расширение Lesson)"""

    lesson = models.OneToOneField(
        Lesson,
        on_delete=models.CASCADE,
        related_name='videolesson',
        verbose_name='Урок'
    )

    vimeo_video_id = models.CharField(
        'ID видео Vimeo',
        max_length=100,
        help_text='Например: 123456789'
    )

    video_duration = models.PositiveIntegerField(
        'Длительность видео (секунды)',
        validators=[MinValueValidator(1)]
    )

    completion_threshold = models.PositiveIntegerField(
        'Порог завершения (%)',
        default=90,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text='Процент просмотра для завершения урока'
    )

    timecodes = models.JSONField(
        'Таймкоды',
        default=list,
        blank=True,
        help_text='Список таймкодов: [{"time": 120, "label": "Введение"}]'
    )

    # ✅ ДОБАВИТЬ:
    thumbnail = models.ImageField(
        'Обложка видео',
        upload_to='video_thumbnails/%Y/%m/',
        blank=True,
        null=True,
        help_text='Рекомендуемый размер: 1280x720px'
    )

    class Meta:
        verbose_name = 'Видео-урок'
        verbose_name_plural = 'Видео-уроки'

    def __str__(self):
        return f"Видео: {self.lesson.title}"

    def save(self, *args, **kwargs):
        """Автоматическое сжатие и конвертация обложки в WebP"""
        if self.thumbnail:
            self.thumbnail = self._compress_thumbnail(self.thumbnail)
        super().save(*args, **kwargs)

    def _compress_thumbnail(self, image_field):
        """Сжать и конвертировать изображение в WebP"""
        img = Image.open(image_field)

        # Конвертируем в RGB (WebP не поддерживает RGBA с хорошим сжатием)
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # Ресайз если слишком большое (макс 1920 по ширине)
        max_width = 1920
        if img.width > max_width:
            ratio = max_width / img.width
            new_size = (max_width, int(img.height * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        # Сохраняем в WebP с качеством 85
        output = BytesIO()
        img.save(output, format='WEBP', quality=85, method=6)
        output.seek(0)

        # Создаем новый файл
        filename = image_field.name.rsplit('.', 1)[0] + '.webp'
        return InMemoryUploadedFile(
            output,
            'ImageField',
            filename,
            'image/webp',
            sys.getsizeof(output),
            None
        )

    def get_vimeo_embed_url(self):
        """Получить URL для embed Vimeo"""
        return f"https://player.vimeo.com/video/{self.vimeo_video_id}"

    def format_duration(self):
        """Форматировать длительность в читаемый вид"""
        minutes = self.video_duration // 60
        seconds = self.video_duration % 60
        return f"{minutes}:{seconds:02d}"


class TextLesson(models.Model):
    """Текстовый урок (расширение Lesson)"""

    lesson = models.OneToOneField(
        Lesson,
        on_delete=models.CASCADE,
        related_name='textlesson',
        verbose_name='Урок'
    )

    content = models.TextField('Содержимое урока')

    estimated_reading_time = models.PositiveIntegerField(
        'Время чтения (минуты)',
        default=5,
        validators=[MinValueValidator(1)],
        help_text='Примерное время на чтение'
    )

    class Meta:
        verbose_name = 'Текстовый урок'
        verbose_name_plural = 'Текстовые уроки'

    def __str__(self):
        return f"Текст: {self.lesson.title}"

    def get_word_count(self):
        """Количество слов в уроке"""
        return len(self.content.split())


class LessonMaterial(models.Model):
    """Дополнительные материалы к уроку"""

    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name='materials',
        verbose_name='Урок'
    )

    title = models.CharField('Название материала', max_length=255)
    description = models.TextField('Описание', blank=True)

    file = models.FileField(
        'Файл',
        upload_to='lesson_materials/%Y/%m/',
        blank=True,
        null=True
    )

    url = models.URLField(
        'Ссылка',
        blank=True,
        help_text='Внешняя ссылка на материал'
    )

    order = models.PositiveIntegerField('Порядок', default=0)

    created_at = models.DateTimeField('Создан', auto_now_add=True)

    class Meta:
        verbose_name = 'Материал к уроку'
        verbose_name_plural = 'Материалы к уроку'
        ordering = ['lesson', 'order']

    def __str__(self):
        return f"{self.lesson.title} - {self.title}"

    def get_file_size(self):
        """Размер файла в читаемом виде"""
        if self.file:
            size = self.file.size
            for unit in ['Б', 'КБ', 'МБ', 'ГБ']:
                if size < 1024.0:
                    return f"{size:.1f} {unit}"
                size /= 1024.0
        return None