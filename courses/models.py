from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


class Course(models.Model):
    """Модель курса"""

    title = models.CharField('Название курса', max_length=255)
    description = models.TextField('Описание курса', blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_courses',
        verbose_name='Создатель'
    )

    is_active = models.BooleanField('Активен', default=True)
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)

    class Meta:
        verbose_name = 'Курс'
        verbose_name_plural = 'Курсы'
        db_table = 'courses'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def get_total_lessons(self):
        """Общее количество уроков в курсе"""
        return self.lessons.count()

    def get_enrolled_students_count(self):
        """Количество записанных студентов"""
        return self.enrollments.count()


class Lesson(models.Model):
    """Модель урока"""

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='lessons',
        verbose_name='Курс'
    )

    title = models.CharField('Название урока', max_length=255)
    description = models.TextField('Описание урока', blank=True)
    content = models.TextField('Контент урока', blank=True)

    # Новые поля для видео и материалов
    video_url = models.URLField('Ссылка на видео', blank=True, null=True, help_text='Ссылка на YouTube, Vimeo и т.д.')
    video_duration = models.PositiveIntegerField('Длительность видео (сек)', blank=True, null=True,
                                                 help_text='Длительность в секундах')
    timecodes = models.JSONField('Таймкоды', blank=True, null=True,
                                 help_text='JSON массив таймкодов: [{"time": "00:00", "title": "Введение"}]')

    order = models.PositiveIntegerField(
        'Порядковый номер',
        default=0,
        help_text='Порядок урока в курсе'
    )

    requires_previous_completion = models.BooleanField(
        'Требует завершения предыдущего',
        default=False,
        help_text='Если включено, урок будет доступен только после завершения предыдущего'
    )

    is_active = models.BooleanField('Активен', default=True)
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)

    class Meta:
        verbose_name = 'Урок'
        verbose_name_plural = 'Уроки'
        db_table = 'lessons'
        ordering = ['course', 'order']
        unique_together = [['course', 'order']]

    def __str__(self):
        return f"{self.course.title} - {self.order}. {self.title}"

    def get_previous_lesson(self):
        """Получить предыдущий урок"""
        return Lesson.objects.filter(
            course=self.course,
            order__lt=self.order
        ).order_by('-order').first()


class CourseEnrollment(models.Model):
    """Запись студента на курс"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='course_enrollments',
        verbose_name='Студент'
    )

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='enrollments',
        verbose_name='Курс'
    )

    enrolled_at = models.DateTimeField('Дата записи', auto_now_add=True)

    class Meta:
        verbose_name = 'Запись на курс'
        verbose_name_plural = 'Записи на курсы'
        db_table = 'course_enrollments'
        unique_together = [['user', 'course']]
        ordering = ['-enrolled_at']

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.course.title}"

    def get_progress_percentage(self):
        """Получить процент прогресса по курсу"""
        total_lessons = self.course.get_total_lessons()
        if total_lessons == 0:
            return 0

        completed_lessons = LessonProgress.objects.filter(
            user=self.user,
            lesson__course=self.course,
            is_completed=True
        ).count()

        return round((completed_lessons / total_lessons) * 100, 2)


class LessonProgress(models.Model):
    """Прогресс студента по уроку"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='lesson_progress',
        verbose_name='Студент'
    )

    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name='progress',
        verbose_name='Урок'
    )

    is_completed = models.BooleanField('Завершен', default=False)
    started_at = models.DateTimeField('Дата начала', auto_now_add=True)
    completed_at = models.DateTimeField('Дата завершения', null=True, blank=True)

    class Meta:
        verbose_name = 'Прогресс по уроку'
        verbose_name_plural = 'Прогресс по урокам'
        db_table = 'lesson_progress'
        unique_together = [['user', 'lesson']]
        ordering = ['lesson__course', 'lesson__order']

    def __str__(self):
        status = "Завершен" if self.is_completed else "В процессе"
        return f"{self.user.get_full_name()} - {self.lesson.title} ({status})"

    def save(self, *args, **kwargs):
        """При отметке как завершенный - сохранить дату завершения"""
        if self.is_completed and not self.completed_at:
            self.completed_at = timezone.now()
        super().save(*args, **kwargs)


class LessonMaterial(models.Model):
    """Материалы урока (файлы, ссылки)"""

    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name='materials',
        verbose_name='Урок'
    )

    title = models.CharField('Название материала', max_length=255)
    description = models.TextField('Описание', blank=True)

    # Либо файл, либо ссылка
    file = models.FileField('Файл', upload_to='lesson_materials/%Y/%m/', blank=True, null=True)
    url = models.URLField('Ссылка', blank=True, null=True)

    file_size = models.PositiveIntegerField('Размер файла (байт)', blank=True, null=True)
    file_type = models.CharField('Тип файла', max_length=50, blank=True)

    order = models.PositiveIntegerField('Порядок отображения', default=0)

    created_at = models.DateTimeField('Дата создания', auto_now_add=True)

    class Meta:
        verbose_name = 'Материал урока'
        verbose_name_plural = 'Материалы уроков'
        db_table = 'lesson_materials'
        ordering = ['lesson', 'order']

    def __str__(self):
        return f"{self.lesson.title} - {self.title}"

    def save(self, *args, **kwargs):
        """Автоматически определить размер и тип файла"""
        if self.file:
            self.file_size = self.file.size
            self.file_type = self.file.name.split('.')[-1].lower()
        super().save(*args, **kwargs)