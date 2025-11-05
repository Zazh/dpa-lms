from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


class Course(models.Model):
    """Модель курса"""

    title = models.CharField('Название курса', max_length=255)
    label = models.CharField('Label', max_length=50, blank=True,)
    duration = models.DecimalField(
        verbose_name='Длительность (часы)',
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
    )
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


class Module(models.Model):
    """Модуль курса - группа уроков"""

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='modules',
        verbose_name='Курс'
    )

    title = models.CharField('Название модуля', max_length=255)
    description = models.TextField('Описание модуля', blank=True)

    order = models.PositiveIntegerField(
        'Порядковый номер',
        default=0,
        help_text='Порядок модуля в курсе'
    )

    # Настройки доступа к модулю
    requires_previous_module = models.BooleanField(
        'Требует завершения предыдущего модуля',
        default=True,
        help_text='Модуль доступен только после завершения предыдущего'
    )

    is_active = models.BooleanField('Активен', default=True)
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)

    class Meta:
        verbose_name = 'Модуль'
        verbose_name_plural = 'Модули'
        db_table = 'modules'
        ordering = ['course', 'order']
        unique_together = [['course', 'order']]

    def __str__(self):
        return f"{self.course.title} - Модуль {self.order}: {self.title}"

    def get_total_lessons(self):
        """Количество уроков в модуле"""
        return self.lessons.filter(is_active=True).count()

    def get_previous_module(self):
        """Получить предыдущий модуль"""
        return Module.objects.filter(
            course=self.course,
            order__lt=self.order
        ).order_by('-order').first()


class Lesson(models.Model):
    """Модель урока (базовая)"""

    # Типы уроков
    LESSON_TYPES = [
        ('video', 'Видео урок'),
        ('text', 'Текстовый урок'),
        ('quiz', 'Тест'),
        ('assignment', 'Домашнее задание'),
    ]

    module = models.ForeignKey(
        'Module',  # ← Используем строку, чтобы избежать проблем с порядком определения
        on_delete=models.CASCADE,
        related_name='lessons',
        verbose_name='Модуль',
        null=True,
        blank=True,
    )

    # ← НОВОЕ: Задержка доступа
    access_delay_hours = models.PositiveIntegerField(
        'Задержка доступа (часы)',
        default=0,
        help_text='Через сколько часов урок станет доступен после завершения предыдущего. 0 = доступен сразу'
    )

    lesson_type = models.CharField(
        'Тип урока',
        max_length=20,
        choices=LESSON_TYPES,
        default='video',
        db_index=True
    )

    title = models.CharField('Название урока', max_length=255)
    description = models.TextField('Описание урока', blank=True)

    # Контент для текстовых уроков (оставляем для совместимости)
    content = models.TextField('Контент урока', blank=True)

    # Поля для видео (оставляем для обратной совместимости)
    video_url = models.URLField('Ссылка на видео', blank=True, null=True)
    video_duration = models.PositiveIntegerField('Длительность видео (сек)', blank=True, null=True)
    timecodes = models.JSONField('Таймкоды', blank=True, null=True)

    order = models.PositiveIntegerField(
        'Порядковый номер',
        default=0,
        help_text='Порядок урока в модуле'
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
        ordering = ['module', 'order']  # ← ИСПРАВЛЕНО: module вместо course
        unique_together = [['module', 'order']]  # ← ИСПРАВЛЕНО: module вместо course

    def __str__(self):
        if self.module:
            return f"{self.module.course.title} - Модуль {self.module.order} - {self.order}. {self.title}"
        return f"Урок {self.order}: {self.title}"

    def get_previous_lesson(self):
        """Получить предыдущий урок в этом модуле"""
        return Lesson.objects.filter(
            module=self.module,  # ← ИСПРАВЛЕНО
            order__lt=self.order
        ).order_by('-order').first()

    def get_lesson_type_display_icon(self):
        """Получить иконку типа урока"""
        icons = {
            'video': '🎥',
            'text': '📝',
            'quiz': '📋',
            'assignment': '📂'
        }
        return icons.get(self.lesson_type, '❓')

    def get_content_object(self):
        """Получить объект контента в зависимости от типа урока"""
        if self.lesson_type == 'video':
            return getattr(self, 'video_content', None)
        elif self.lesson_type == 'text':
            return getattr(self, 'text_content', None)
        elif self.lesson_type == 'quiz':
            return getattr(self, 'quiz_content', None)
        elif self.lesson_type == 'assignment':
            return getattr(self, 'assignment_content', None)
        return None

    # ============================================================
    # ← НОВЫЙ МЕТОД: Проверка доступа к уроку
    # ============================================================

    def get_access_status(self, user):
        """
        Получить статус доступа к уроку для пользователя

        Args:
            user: объект пользователя

        Returns:
            dict: {
                'status': 'completed' | 'available' | 'locked' | 'unavailable',
                'available_at': datetime or None,
                'time_remaining_seconds': int or None,
                'message': str
            }
        """
        from datetime import timedelta

        # 1. Проверяем, завершен ли урок
        progress = LessonProgress.objects.filter(user=user, lesson=self).first()
        if progress and progress.is_completed:
            return {
                'status': 'completed',
                'available_at': None,
                'time_remaining_seconds': None,
                'message': 'Урок пройден'
            }

        # 2. Проверяем требование завершения предыдущего урока
        if self.requires_previous_completion:
            previous_lesson = self.get_previous_lesson()

            if previous_lesson:
                prev_progress = LessonProgress.objects.filter(
                    user=user,
                    lesson=previous_lesson
                ).first()

                # Предыдущий урок не завершен
                if not prev_progress or not prev_progress.is_completed:
                    return {
                        'status': 'unavailable',
                        'available_at': None,
                        'time_remaining_seconds': None,
                        'message': f'Сначала завершите урок: {previous_lesson.title}'
                    }

                # Предыдущий завершен, проверяем задержку
                if self.access_delay_hours > 0:
                    available_at = prev_progress.completed_at + timedelta(hours=self.access_delay_hours)
                    now = timezone.now()

                    if now < available_at:
                        time_remaining = available_at - now
                        time_remaining_seconds = int(time_remaining.total_seconds())

                        # Форматируем сообщение
                        hours = time_remaining_seconds // 3600
                        minutes = (time_remaining_seconds % 3600) // 60

                        if hours > 0:
                            time_str = f"{hours} ч {minutes} мин"
                        else:
                            time_str = f"{minutes} мин"

                        return {
                            'status': 'locked',
                            'available_at': available_at.isoformat(),
                            'time_remaining_seconds': time_remaining_seconds,
                            'message': f'Урок будет доступен через {time_str}'
                        }

        # 3. Урок доступен
        return {
            'status': 'available',
            'available_at': None,
            'time_remaining_seconds': None,
            'message': 'Урок доступен для прохождения'
        }


# ============================================================
# РАСШИРЕНИЯ ДЛЯ РАЗНЫХ ТИПОВ УРОКОВ
# ============================================================

class VideoLesson(models.Model):
    """Расширение для видео урока"""

    lesson = models.OneToOneField(
        Lesson,
        on_delete=models.CASCADE,
        related_name='video_content',
        limit_choices_to={'lesson_type': 'video'},
        verbose_name='Урок'
    )

    # Vimeo настройки
    vimeo_video_id = models.CharField(
        'Vimeo Video ID',
        max_length=50,
        help_text='ID видео из Vimeo (например: 123456789)'
    )
    video_duration = models.PositiveIntegerField(
        'Длительность видео (секунды)',
        help_text='Длительность в секундах'
    )

    # Настройка завершения
    completion_threshold = models.PositiveIntegerField(
        'Порог завершения (%)',
        default=90,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text='Процент просмотра для автоматического завершения урока'
    )

    # Таймкоды
    timecodes = models.JSONField(
        'Таймкоды',
        blank=True,
        null=True,
        help_text='JSON формат: [{"time": "00:30", "title": "Введение"}, {"time": "05:15", "title": "Основы"}]'
    )

    # Дополнительные настройки
    allow_speed_control = models.BooleanField(
        'Разрешить управление скоростью',
        default=True
    )
    allow_download = models.BooleanField(
        'Разрешить скачивание',
        default=False
    )

    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)

    class Meta:
        verbose_name = 'Видео урок'
        verbose_name_plural = 'Видео уроки'
        db_table = 'video_lessons'

    def __str__(self):
        if self.lesson and self.lesson.module:
            return f"Видео: {self.lesson.module.course.title} - {self.lesson.title}"
        return f"Видео: {self.lesson.title if self.lesson else 'Без урока'}"

    def get_vimeo_embed_url(self):
        """Получить URL для встраивания Vimeo"""
        return f"https://player.vimeo.com/video/{self.vimeo_video_id}"


class TextLesson(models.Model):
    """Расширение для текстового урока"""

    lesson = models.OneToOneField(
        Lesson,
        on_delete=models.CASCADE,
        related_name='text_content',
        limit_choices_to={'lesson_type': 'text'},
        verbose_name='Урок'
    )

    # Основной контент
    content = models.TextField(
        'Текстовый контент',
        help_text='Основной текст урока (поддерживает Markdown или HTML)'
    )

    # Метаданные
    estimated_reading_time = models.PositiveIntegerField(
        'Время на чтение (минуты)',
        default=5,
        help_text='Примерное время для прочтения материала'
    )
    word_count = models.PositiveIntegerField(
        'Количество слов',
        default=0,
        editable=False,
        help_text='Автоматически рассчитывается'
    )

    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)

    class Meta:
        verbose_name = 'Текстовый урок'
        verbose_name_plural = 'Текстовые уроки'
        db_table = 'text_lessons'

    def __str__(self):
        if self.lesson and self.lesson.module:
            return f"Текст: {self.lesson.module.course.title} - {self.lesson.title}"
        return f"Текст: {self.lesson.title if self.lesson else 'Без урока'}"

    def save(self, *args, **kwargs):
        """Автоматически рассчитать количество слов"""
        if self.content:
            self.word_count = len(self.content.split())
        super().save(*args, **kwargs)


class QuizLesson(models.Model):
    """Расширение для теста"""

    lesson = models.OneToOneField(
        Lesson,
        on_delete=models.CASCADE,
        related_name='quiz_content',
        limit_choices_to={'lesson_type': 'quiz'},
        verbose_name='Урок'
    )

    # Настройки прохождения
    passing_score = models.PositiveIntegerField(
        'Проходной балл (%)',
        default=70,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text='Минимальный процент правильных ответов для прохождения'
    )
    max_attempts = models.PositiveIntegerField(
        'Максимум попыток',
        default=2,
        validators=[MinValueValidator(1)],
        help_text='Количество попыток для прохождения теста'
    )
    retry_delay_hours = models.PositiveIntegerField(
        'Задержка между попытками (часы)',
        default=24,
        help_text='Время блокировки после неудачной попытки'
    )

    # Ограничение по времени
    time_limit_minutes = models.PositiveIntegerField(
        'Время на тест (минуты)',
        null=True,
        blank=True,
        help_text='Оставьте пустым для неограниченного времени'
    )

    # Настройки отображения
    show_correct_answers = models.BooleanField(
        'Показывать правильные ответы',
        default=True,
        help_text='Показывать правильные ответы после успешного прохождения'
    )
    show_incorrect_only = models.BooleanField(
        'Показывать только неправильные',
        default=True,
        help_text='Если включено, показывать только те вопросы, на которые ответили неправильно'
    )
    show_score_immediately = models.BooleanField(
        'Показывать результат сразу',
        default=True,
        help_text='Показывать результат сразу после завершения теста'
    )

    # Рандомизация
    shuffle_questions = models.BooleanField(
        'Перемешивать вопросы',
        default=False,
        help_text='Вопросы будут в случайном порядке'
    )
    shuffle_answers = models.BooleanField(
        'Перемешивать ответы',
        default=True,
        help_text='Варианты ответов будут в случайном порядке'
    )

    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)

    class Meta:
        verbose_name = 'Тест'
        verbose_name_plural = 'Тесты'
        db_table = 'quiz_lessons'

    def __str__(self):
        if self.lesson and self.lesson.module:
            return f"Тест: {self.lesson.module.course.title} - {self.lesson.title}"
        return f"Тест: {self.lesson.title if self.lesson else 'Без урока'}"

    def get_total_questions(self):
        """Общее количество вопросов"""
        return self.questions.count()


class AssignmentLesson(models.Model):
    """Расширение для домашнего задания"""

    lesson = models.OneToOneField(
        Lesson,
        on_delete=models.CASCADE,
        related_name='assignment_content',
        limit_choices_to={'lesson_type': 'assignment'},
        verbose_name='Урок'
    )

    # Инструкции
    instructions = models.TextField(
        'Инструкции к заданию',
        help_text='Детальное описание того, что нужно сделать'
    )

    # ← НОВЫЕ ПОЛЯ: Требования к ответу
    require_text = models.BooleanField(
        'Текст обязателен',
        default=False,
        help_text='Студент должен заполнить текстовое поле'
    )

    require_file = models.BooleanField(
        'Файл обязателен',
        default=True,
        help_text='Студент должен загрузить файл'
    )

    # Оценка
    max_score = models.PositiveIntegerField(
        'Максимальный балл',
        default=100,
        help_text='Максимальная оценка за задание'
    )

    # Дедлайн
    deadline = models.DateTimeField(
        'Дедлайн',
        null=True,
        blank=True,
        help_text='Крайний срок сдачи (оставьте пустым если нет дедлайна)'
    )
    allow_late_submission = models.BooleanField(
        'Разрешить опоздание',
        default=True,
        help_text='Можно ли сдать задание после дедлайна'
    )
    late_penalty_percent = models.PositiveIntegerField(
        'Штраф за опоздание (%)',
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='Процент снижения оценки за просрочку'
    )

    # Настройки пересдачи
    allow_resubmission = models.BooleanField(
        'Разрешить пересдачу',
        default=True,
        help_text='Можно ли отправлять задание на доработку и пересдачу'
    )
    max_resubmissions = models.PositiveIntegerField(
        'Максимум пересдач',
        default=3,
        help_text='Максимальное количество попыток сдачи (0 = неограничено)'
    )

    # Настройки файлов
    allowed_file_types = models.CharField(
        'Разрешенные форматы файлов',
        max_length=255,
        blank=True,
        help_text='Через запятую: pdf,docx,jpg,png (оставьте пустым для любых)'
    )
    max_file_size_mb = models.PositiveIntegerField(
        'Макс. размер файла (МБ)',
        default=10,
        help_text='Максимальный размер загружаемого файла в мегабайтах'
    )

    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)

    class Meta:
        verbose_name = 'Домашнее задание'
        verbose_name_plural = 'Домашние задания'
        db_table = 'assignment_lessons'

    def __str__(self):
        if self.lesson and self.lesson.module:
            return f"ДЗ: {self.lesson.module.course.title} - {self.lesson.title}"
        return f"ДЗ: {self.lesson.title if self.lesson else 'Без урока'}"

    def is_deadline_passed(self):
        """Проверка, прошел ли дедлайн"""
        if not self.deadline:
            return False
        return timezone.now() > self.deadline

    def get_allowed_extensions(self):
        """Получить список разрешенных расширений"""
        if not self.allowed_file_types:
            return []
        return [ext.strip() for ext in self.allowed_file_types.split(',')]


# ============================================================
# МОДЕЛИ ДЛЯ КВИЗОВ (ТЕСТОВ)
# ============================================================

class QuizQuestion(models.Model):
    """Вопрос теста"""

    QUESTION_TYPES = [
        ('single', 'Один правильный ответ'),
        ('multiple', 'Несколько правильных ответов'),
    ]

    quiz = models.ForeignKey(
        QuizLesson,
        on_delete=models.CASCADE,
        related_name='questions',
        verbose_name='Тест'
    )

    question_type = models.CharField(
        'Тип вопроса',
        max_length=20,
        choices=QUESTION_TYPES,
        default='single'
    )

    question_text = models.TextField(
        'Текст вопроса',
        help_text='Формулировка вопроса'
    )

    explanation = models.TextField(
        'Пояснение к ответу',
        blank=True,
        help_text='Объяснение правильного ответа (показывается после прохождения)'
    )

    points = models.PositiveIntegerField(
        'Баллы за вопрос',
        default=1,
        help_text='Количество баллов за правильный ответ'
    )

    order = models.PositiveIntegerField(
        'Порядок',
        default=0,
        help_text='Порядок отображения вопроса'
    )

    is_active = models.BooleanField('Активен', default=True)
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)

    class Meta:
        verbose_name = 'Вопрос теста'
        verbose_name_plural = 'Вопросы теста'
        db_table = 'quiz_questions'
        ordering = ['quiz', 'order']

    def __str__(self):
        return f"{self.quiz.lesson.title} - Вопрос {self.order}: {self.question_text[:50]}"

    def get_correct_answers(self):
        """Получить все правильные ответы"""
        return self.answers.filter(is_correct=True)

    def check_answer(self, selected_answer_ids):
        """
        Проверить правильность ответа студента

        Args:
            selected_answer_ids: список ID выбранных ответов

        Returns:
            bool: True если ответ правильный
        """
        correct_ids = set(self.get_correct_answers().values_list('id', flat=True))
        selected_ids = set(selected_answer_ids)

        return correct_ids == selected_ids


class QuizAnswer(models.Model):
    """Вариант ответа на вопрос"""

    question = models.ForeignKey(
        QuizQuestion,
        on_delete=models.CASCADE,
        related_name='answers',
        verbose_name='Вопрос'
    )

    answer_text = models.CharField(
        'Текст ответа',
        max_length=500,
        help_text='Вариант ответа'
    )

    is_correct = models.BooleanField(
        'Правильный ответ',
        default=False,
        help_text='Отметьте если это правильный ответ'
    )

    order = models.PositiveIntegerField(
        'Порядок',
        default=0,
        help_text='Порядок отображения ответа'
    )

    created_at = models.DateTimeField('Дата создания', auto_now_add=True)

    class Meta:
        verbose_name = 'Вариант ответа'
        verbose_name_plural = 'Варианты ответов'
        db_table = 'quiz_answers'
        ordering = ['question', 'order']

    def __str__(self):
        mark = "✓" if self.is_correct else "✗"
        return f"[{mark}] {self.answer_text[:30]}"


class QuizAttempt(models.Model):
    """Попытка прохождения теста (история всех попыток)"""

    STATUS_CHOICES = [
        ('in_progress', 'В процессе'),
        ('completed', 'Завершена'),
        ('passed', 'Пройдена'),
        ('failed', 'Не пройдена'),
        ('expired', 'Время истекло'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='quiz_attempts',
        verbose_name='Студент'
    )

    quiz = models.ForeignKey(
        QuizLesson,
        on_delete=models.CASCADE,
        related_name='attempts',
        verbose_name='Тест'
    )

    # Номер попытки
    attempt_number = models.PositiveIntegerField(
        'Номер попытки',
        help_text='Порядковый номер попытки для этого студента'
    )

    # Статус
    status = models.CharField(
        'Статус',
        max_length=20,
        choices=STATUS_CHOICES,
        default='in_progress',
        db_index=True
    )

    # Даты
    started_at = models.DateTimeField('Начало', auto_now_add=True)
    completed_at = models.DateTimeField('Завершение', null=True, blank=True)
    expires_at = models.DateTimeField(
        'Истекает',
        null=True,
        blank=True,
        help_text='Время окончания теста (если есть ограничение)'
    )

    # Результаты
    total_questions = models.PositiveIntegerField('Всего вопросов', default=0)
    correct_answers = models.PositiveIntegerField('Правильных ответов', default=0)
    total_points = models.PositiveIntegerField('Всего баллов', default=0)
    earned_points = models.PositiveIntegerField('Заработано баллов', default=0)

    score_percentage = models.DecimalField(
        'Результат (%)',
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Процент правильных ответов'
    )

    # Блокировка следующей попытки
    can_retry_at = models.DateTimeField(
        'Доступна следующая попытка',
        null=True,
        blank=True,
        help_text='Время, когда можно будет пройти тест снова'
    )

    class Meta:
        verbose_name = 'Попытка теста'
        verbose_name_plural = 'Попытки тестов'
        db_table = 'quiz_attempts'
        ordering = ['-started_at']
        unique_together = [['user', 'quiz', 'attempt_number']]
        indexes = [
            models.Index(fields=['user', 'quiz', '-started_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.quiz.lesson.title} (попытка {self.attempt_number})"

    def save(self, *args, **kwargs):
        """Установить время истечения при создании"""
        if not self.pk and self.quiz.time_limit_minutes:
            from datetime import timedelta
            self.expires_at = timezone.now() + timedelta(minutes=self.quiz.time_limit_minutes)
        super().save(*args, **kwargs)

    def is_expired(self):
        """Проверка, истекло ли время теста"""
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at and self.status == 'in_progress'

    def calculate_score(self):
        """
        Подсчет результата попытки
        Вызывается после того, как студент ответил на все вопросы
        """
        from datetime import timedelta

        # Получаем все ответы студента
        responses = self.responses.all()

        # Подсчет статистики
        self.total_questions = responses.count()
        self.correct_answers = responses.filter(is_correct=True).count()

        # Подсчет баллов
        self.total_points = sum(r.question.points for r in responses)
        self.earned_points = sum(r.points_earned for r in responses)

        # Процент правильных ответов
        if self.total_questions > 0:
            self.score_percentage = (self.correct_answers / self.total_questions) * 100
        else:
            self.score_percentage = 0

        # Определение статуса
        if self.score_percentage >= self.quiz.passing_score:
            self.status = 'passed'
        else:
            self.status = 'failed'
            # Установка времени блокировки следующей попытки
            self.can_retry_at = timezone.now() + timedelta(hours=self.quiz.retry_delay_hours)

        self.completed_at = timezone.now()
        self.save()

        # Если тест пройден - отметить урок как завершенный
        if self.status == 'passed':
            lesson_progress, created = LessonProgress.objects.get_or_create(
                user=self.user,
                lesson=self.quiz.lesson
            )
            if not lesson_progress.is_completed:
                lesson_progress.mark_completed(data={
                    'quiz_attempt_id': self.id,
                    'score': float(self.score_percentage),
                    'attempt_number': self.attempt_number
                })

    def get_incorrect_responses(self):
        """Получить неправильные ответы (для показа студенту)"""
        return self.responses.filter(is_correct=False)

    def can_view_results(self):
        """Можно ли показать результаты студенту"""
        return self.status in ['passed', 'failed', 'completed']


class QuizResponse(models.Model):
    """Ответ студента на вопрос теста"""

    attempt = models.ForeignKey(
        QuizAttempt,
        on_delete=models.CASCADE,
        related_name='responses',
        verbose_name='Попытка'
    )

    question = models.ForeignKey(
        QuizQuestion,
        on_delete=models.CASCADE,
        verbose_name='Вопрос'
    )

    selected_answers = models.ManyToManyField(
        QuizAnswer,
        related_name='student_responses',
        verbose_name='Выбранные ответы',
        help_text='Ответы, которые выбрал студент'
    )

    is_correct = models.BooleanField(
        'Правильно',
        default=False,
        help_text='Правильно ли ответил студент'
    )

    points_earned = models.PositiveIntegerField(
        'Заработано баллов',
        default=0,
        help_text='Баллы за этот ответ'
    )

    answered_at = models.DateTimeField('Время ответа', auto_now_add=True)

    class Meta:
        verbose_name = 'Ответ на вопрос'
        verbose_name_plural = 'Ответы на вопросы'
        db_table = 'quiz_responses'
        unique_together = [['attempt', 'question']]
        ordering = ['attempt', 'question__order']

    def __str__(self):
        mark = "✓" if self.is_correct else "✗"
        return f"[{mark}] {self.attempt.user.get_full_name()} - {self.question.question_text[:30]}"

    def check_and_save_answer(self, selected_answer_ids):
        """
        Проверить ответ и сохранить результат

        Args:
            selected_answer_ids: список ID выбранных ответов
        """
        # Проверка правильности
        self.is_correct = self.question.check_answer(selected_answer_ids)

        # Начисление баллов
        if self.is_correct:
            self.points_earned = self.question.points
        else:
            self.points_earned = 0

        self.save()

        # Добавление выбранных ответов
        self.selected_answers.set(selected_answer_ids)


# ============================================================
# МОДЕЛИ ДЛЯ ДОМАШНИХ ЗАДАНИЙ
# ============================================================

class AssignmentSubmission(models.Model):
    """Сдача домашнего задания студентом"""

    STATUS_CHOICES = [
        ('draft', 'Черновик'),
        ('submitted', 'Отправлено на проверку'),
        ('in_review', 'На проверке'),
        ('revision_requested', 'Требуется доработка'),
        ('approved', 'Принято'),
        ('rejected', 'Отклонено'),
    ]

    assignment = models.ForeignKey(
        AssignmentLesson,
        on_delete=models.CASCADE,
        related_name='submissions',
        verbose_name='Домашнее задание'
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='assignment_submissions',
        verbose_name='Студент'
    )

    # Номер попытки (для пересдач)
    submission_number = models.PositiveIntegerField(
        'Номер попытки',
        default=1,
        help_text='Порядковый номер сдачи (при пересдачах увеличивается)'
    )

    # Работа студента (текст и/или файл - в зависимости от настроек)
    submission_text = models.TextField(
        'Текстовый ответ',
        blank=True,
        help_text='Текстовый ответ студента на задание'
    )

    submission_file = models.FileField(
        'Файл работы',
        upload_to='assignments/%Y/%m/',
        blank=True,
        null=True,
        help_text='Загруженный файл с выполненным заданием'
    )

    # Статус
    status = models.CharField(
        'Статус',
        max_length=30,
        choices=STATUS_CHOICES,
        default='draft',
        db_index=True
    )

    # Даты
    created_at = models.DateTimeField(
        'Создано',
        auto_now_add=True,
        help_text='Когда создан черновик'
    )

    submitted_at = models.DateTimeField(
        'Отправлено на проверку',
        null=True,
        blank=True,
        help_text='Когда отправлено на проверку'
    )

    reviewed_at = models.DateTimeField(
        'Проверено',
        null=True,
        blank=True,
        help_text='Когда инструктор проверил'
    )

    # Оценка от инструктора
    score = models.PositiveIntegerField(
        'Оценка',
        null=True,
        blank=True,
        help_text='Оценка за работу (из max_score задания)'
    )

    feedback = models.TextField(
        'Отзыв инструктора',
        blank=True,
        help_text='Общий отзыв инструктора о работе'
    )

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_assignments',
        verbose_name='Проверил'
    )

    # Метаданные
    is_late = models.BooleanField(
        'Опоздание',
        default=False,
        help_text='Было ли опоздание при сдаче'
    )

    class Meta:
        verbose_name = 'Сдача ДЗ'
        verbose_name_plural = 'Сдачи ДЗ'
        db_table = 'assignment_submissions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'assignment', '-created_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.assignment.lesson.title} (попытка {self.submission_number})"

    def clean(self):
        """Валидация в зависимости от требований задания"""
        from django.core.exceptions import ValidationError

        errors = {}

        # Проверка обязательности текста
        if self.assignment.require_text and not self.submission_text:
            errors['submission_text'] = 'Текстовый ответ обязателен для этого задания'

        # Проверка обязательности файла
        if self.assignment.require_file and not self.submission_file:
            errors['submission_file'] = 'Необходимо загрузить файл для этого задания'

        # Хотя бы одно из полей должно быть заполнено
        if not self.submission_text and not self.submission_file:
            errors['__all__'] = 'Необходимо заполнить текстовый ответ или загрузить файл'

        # Валидация файла, если он загружен
        if self.submission_file:
            # Проверка размера
            file_size_mb = self.submission_file.size / (1024 * 1024)
            if file_size_mb > self.assignment.max_file_size_mb:
                errors['submission_file'] = f'Размер файла не должен превышать {self.assignment.max_file_size_mb} МБ'

            # Проверка расширения
            ext = self.submission_file.name.split('.')[-1].lower()
            allowed = self.assignment.get_allowed_extensions()
            if allowed and ext not in allowed:
                errors['submission_file'] = f'Разрешены только файлы: {", ".join(allowed)}'

        if errors:
            raise ValidationError(errors)

    def check_if_late(self):
        """Проверить и установить флаг опоздания"""
        if self.assignment.deadline and self.submitted_at:
            self.is_late = self.submitted_at > self.assignment.deadline
        else:
            self.is_late = False
        return self.is_late

    def get_penalty_score(self):
        """
        Рассчитать оценку с учетом штрафа за опоздание

        Returns:
            int: Оценка с учетом штрафа
        """
        if not self.score:
            return None

        if self.is_late and self.assignment.late_penalty_percent > 0:
            penalty = (self.score * self.assignment.late_penalty_percent) / 100
            return max(0, int(self.score - penalty))

        return self.score

    def can_resubmit(self):
        """Проверить, можно ли пересдать задание"""
        # Если не разрешена пересдача
        if not self.assignment.allow_resubmission:
            return False

        # Если статус не "требуется доработка"
        if self.status != 'revision_requested':
            return False

        # Если есть лимит пересдач (0 = без лимита)
        if self.assignment.max_resubmissions > 0:
            # Проверяем количество попыток
            total_submissions = AssignmentSubmission.objects.filter(
                assignment=self.assignment,
                user=self.user
            ).count()

            if total_submissions >= self.assignment.max_resubmissions:
                return False

        return True

    def submit_for_review(self):
        """Отправить работу на проверку"""
        if self.status == 'draft':
            self.status = 'submitted'
            self.submitted_at = timezone.now()
            self.check_if_late()
            self.save()

            # TODO: Отправить уведомление инструктору
            return True
        return False

    def approve(self, reviewer, score, feedback=''):
        """
        Принять работу (инструктором)

        Args:
            reviewer: User объект инструктора
            score: оценка
            feedback: отзыв
        """
        self.status = 'approved'
        self.score = score
        self.feedback = feedback
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.save()

        # Отметить урок как завершенный
        lesson_progress, created = LessonProgress.objects.get_or_create(
            user=self.user,
            lesson=self.assignment.lesson
        )

        if not lesson_progress.is_completed:
            lesson_progress.mark_completed(data={
                'assignment_submission_id': self.id,
                'score': score,
                'submission_number': self.submission_number
            })

        # TODO: Отправить уведомление студенту

    def request_revision(self, reviewer, feedback):
        """
        Отправить на доработку (инструктором)

        Args:
            reviewer: User объект инструктора
            feedback: что нужно исправить
        """
        self.status = 'revision_requested'
        self.feedback = feedback
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.save()

        # TODO: Отправить уведомление студенту

    def reject(self, reviewer, feedback):
        """
        Отклонить работу (инструктором)

        Args:
            reviewer: User объект инструктора
            feedback: причина отклонения
        """
        self.status = 'rejected'
        self.score = 0
        self.feedback = feedback
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.save()

        # TODO: Отправить уведомление студенту


class AssignmentComment(models.Model):
    """Комментарий к домашнему заданию (система сообщений)"""

    submission = models.ForeignKey(
        AssignmentSubmission,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name='Сдача ДЗ'
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name='Автор'
    )

    # Содержимое комментария (только текст)
    message = models.TextField(
        'Сообщение',
        help_text='Текст комментария/сообщения'
    )

    # Метаданные
    is_instructor = models.BooleanField(
        'От инструктора',
        default=False,
        help_text='Комментарий от инструктора или от студента'
    )

    is_read = models.BooleanField(
        'Прочитано',
        default=False,
        help_text='Прочитано ли сообщение получателем'
    )

    created_at = models.DateTimeField('Дата', auto_now_add=True)

    class Meta:
        verbose_name = 'Комментарий к ДЗ'
        verbose_name_plural = 'Комментарии к ДЗ'
        db_table = 'assignment_comments'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['submission', 'created_at']),
        ]

    def __str__(self):
        author_type = "Инструктор" if self.is_instructor else "Студент"
        return f"[{author_type}] {self.author.get_full_name()}: {self.message[:50]}"

    def save(self, *args, **kwargs):
        """Автоматически определить, от инструктора ли комментарий"""
        if not self.pk:
            # Проверяем, является ли автор преподавателем/админом
            self.is_instructor = self.author.is_staff or self.author.is_superuser

        super().save(*args, **kwargs)

        # TODO: Отправить уведомление получателю (студенту или инструктору)

    def mark_as_read(self):
        """Отметить как прочитанное"""
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=['is_read'])


# ============================================================
# МОДЕЛЬ ДЛЯ ПРОГРЕССА ПРОСМОТРА ВИДЕО
# ============================================================

class VideoProgress(models.Model):
    """Прогресс просмотра видео урока"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='video_progress',
        verbose_name='Студент'
    )

    video_lesson = models.ForeignKey(
        VideoLesson,
        on_delete=models.CASCADE,
        related_name='progress_records',
        verbose_name='Видео урок'
    )

    # Прогресс просмотра
    current_position = models.PositiveIntegerField(
        'Текущая позиция (секунды)',
        default=0,
        help_text='Последняя позиция воспроизведения в секундах'
    )

    watch_percentage = models.DecimalField(
        'Процент просмотра',
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text='Процент просмотренного видео'
    )

    # Статистика
    total_watch_time = models.PositiveIntegerField(
        'Общее время просмотра (секунды)',
        default=0,
        help_text='Суммарное время всех просмотров'
    )

    watch_count = models.PositiveIntegerField(
        'Количество просмотров',
        default=0,
        help_text='Сколько раз студент запускал видео'
    )

    # Завершение
    is_completed = models.BooleanField(
        'Завершен',
        default=False,
        help_text='Достигнут порог завершения'
    )

    completed_at = models.DateTimeField(
        'Дата завершения',
        null=True,
        blank=True,
        help_text='Когда был достигнут порог завершения'
    )

    # Даты
    first_watched_at = models.DateTimeField(
        'Первый просмотр',
        auto_now_add=True,
        help_text='Когда студент впервые начал смотреть видео'
    )

    last_watched_at = models.DateTimeField(
        'Последний просмотр',
        auto_now=True,
        help_text='Последнее обновление прогресса'
    )

    class Meta:
        verbose_name = 'Прогресс видео'
        verbose_name_plural = 'Прогресс видео'
        db_table = 'video_progress'
        unique_together = [['user', 'video_lesson']]
        ordering = ['-last_watched_at']
        indexes = [
            models.Index(fields=['user', 'video_lesson']),
            models.Index(fields=['is_completed']),
        ]

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.video_lesson.lesson.title} ({self.watch_percentage}%)"

    def update_progress(self, current_position, increment_watch_count=False):
        """
        Обновить прогресс просмотра

        Args:
            current_position: текущая позиция в секундах
            increment_watch_count: увеличить счетчик просмотров (при новом запуске видео)
        """
        # Обновляем позицию
        self.current_position = current_position

        # Рассчитываем процент
        if self.video_lesson.video_duration > 0:
            self.watch_percentage = (current_position / self.video_lesson.video_duration) * 100
        else:
            self.watch_percentage = 0

        # Ограничиваем максимум 100%
        if self.watch_percentage > 100:
            self.watch_percentage = 100

        # Увеличиваем счетчик просмотров
        if increment_watch_count:
            self.watch_count += 1

        # Проверяем достижение порога завершения
        if not self.is_completed and self.watch_percentage >= self.video_lesson.completion_threshold:
            self.mark_as_completed()

        self.save()

    def mark_as_completed(self):
        """Отметить видео как завершенное"""
        if not self.is_completed:
            self.is_completed = True
            self.completed_at = timezone.now()

            # Отметить урок как завершенный в LessonProgress
            lesson_progress, created = LessonProgress.objects.get_or_create(
                user=self.user,
                lesson=self.video_lesson.lesson
            )

            if not lesson_progress.is_completed:
                lesson_progress.mark_completed(data={
                    'video_progress_id': self.id,
                    'watch_percentage': float(self.watch_percentage),
                    'total_watch_time': self.total_watch_time
                })

    def add_watch_time(self, seconds):
        """
        Добавить время к общему времени просмотра

        Args:
            seconds: количество секунд для добавления
        """
        self.total_watch_time += seconds
        self.save(update_fields=['total_watch_time'])

    def reset_progress(self):
        """Сбросить прогресс просмотра (например, для повторного просмотра)"""
        self.current_position = 0
        self.watch_percentage = 0
        self.is_completed = False
        self.completed_at = None
        self.save()


# ============================================================
# МОДЕЛЬ ДЛЯ ПРОГРЕССА ПРОСМОТРА ВИДЕО
# ============================================================

class VideoProgress(models.Model):
    """Прогресс просмотра видео урока"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='video_progress',
        verbose_name='Студент'
    )

    video_lesson = models.ForeignKey(
        VideoLesson,
        on_delete=models.CASCADE,
        related_name='progress_records',
        verbose_name='Видео урок'
    )

    # Прогресс просмотра
    current_position = models.PositiveIntegerField(
        'Текущая позиция (секунды)',
        default=0,
        help_text='Последняя позиция воспроизведения в секундах'
    )

    watch_percentage = models.DecimalField(
        'Процент просмотра',
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text='Процент просмотренного видео'
    )

    # Статистика
    total_watch_time = models.PositiveIntegerField(
        'Общее время просмотра (секунды)',
        default=0,
        help_text='Суммарное время всех просмотров'
    )

    watch_count = models.PositiveIntegerField(
        'Количество просмотров',
        default=0,
        help_text='Сколько раз студент запускал видео'
    )

    # Завершение
    is_completed = models.BooleanField(
        'Завершен',
        default=False,
        help_text='Достигнут порог завершения'
    )

    completed_at = models.DateTimeField(
        'Дата завершения',
        null=True,
        blank=True,
        help_text='Когда был достигнут порог завершения'
    )

    # Даты
    first_watched_at = models.DateTimeField(
        'Первый просмотр',
        auto_now_add=True,
        help_text='Когда студент впервые начал смотреть видео'
    )

    last_watched_at = models.DateTimeField(
        'Последний просмотр',
        auto_now=True,
        help_text='Последнее обновление прогресса'
    )

    class Meta:
        verbose_name = 'Прогресс видео'
        verbose_name_plural = 'Прогресс видео'
        db_table = 'video_progress'
        unique_together = [['user', 'video_lesson']]
        ordering = ['-last_watched_at']
        indexes = [
            models.Index(fields=['user', 'video_lesson']),
            models.Index(fields=['is_completed']),
        ]

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.video_lesson.lesson.title} ({self.watch_percentage}%)"

    def update_progress(self, current_position, increment_watch_count=False):
        """
        Обновить прогресс просмотра

        Args:
            current_position: текущая позиция в секундах
            increment_watch_count: увеличить счетчик просмотров (при новом запуске видео)
        """
        # Обновляем позицию
        self.current_position = current_position

        # Рассчитываем процент
        if self.video_lesson.video_duration > 0:
            self.watch_percentage = (current_position / self.video_lesson.video_duration) * 100
        else:
            self.watch_percentage = 0

        # Ограничиваем максимум 100%
        if self.watch_percentage > 100:
            self.watch_percentage = 100

        # Увеличиваем счетчик просмотров
        if increment_watch_count:
            self.watch_count += 1

        # Проверяем достижение порога завершения
        if not self.is_completed and self.watch_percentage >= self.video_lesson.completion_threshold:
            self.mark_as_completed()

        self.save()

    def mark_as_completed(self):
        """Отметить видео как завершенное"""
        if not self.is_completed:
            self.is_completed = True
            self.completed_at = timezone.now()

            # Отметить урок как завершенный в LessonProgress
            lesson_progress, created = LessonProgress.objects.get_or_create(
                user=self.user,
                lesson=self.video_lesson.lesson
            )

            if not lesson_progress.is_completed:
                lesson_progress.mark_completed(data={
                    'video_progress_id': self.id,
                    'watch_percentage': float(self.watch_percentage),
                    'total_watch_time': self.total_watch_time
                })

    def add_watch_time(self, seconds):
        """
        Добавить время к общему времени просмотра

        Args:
            seconds: количество секунд для добавления
        """
        self.total_watch_time += seconds
        self.save(update_fields=['total_watch_time'])

    def reset_progress(self):
        """Сбросить прогресс просмотра (например, для повторного просмотра)"""
        self.current_position = 0
        self.watch_percentage = 0
        self.is_completed = False
        self.completed_at = None
        self.save()


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

    # ← НОВЫЕ ПОЛЯ для кеширования прогресса
    completed_lessons_count = models.PositiveIntegerField(
        'Завершено уроков',
        default=0,
        help_text='Кешированное количество завершенных уроков'
    )

    progress_percentage = models.DecimalField(
        'Прогресс (%)',
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text='Кешированный процент прогресса'
    )

    last_activity_at = models.DateTimeField(
        'Последняя активность',
        null=True,
        blank=True,
        help_text='Когда студент последний раз взаимодействовал с курсом'
    )

    class Meta:
        verbose_name = 'Запись на курс'
        verbose_name_plural = 'Записи на курсы'
        db_table = 'course_enrollments'
        unique_together = [['user', 'course']]
        ordering = ['-enrolled_at']

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.course.title}"

    def get_progress_percentage(self):
        """Получить процент прогресса по курсу (используем кешированное значение)"""
        return self.progress_percentage

    # ← НОВЫЙ МЕТОД
    def update_progress(self):
        """Пересчитать и обновить прогресс по курсу"""
        from .models import LessonProgress

        total_lessons = self.course.get_total_lessons()

        if total_lessons == 0:
            self.completed_lessons_count = 0
            self.progress_percentage = 0
        else:
            completed = LessonProgress.objects.filter(
                user=self.user,
                lesson__course=self.course,
                is_completed=True
            ).count()

            self.completed_lessons_count = completed
            self.progress_percentage = round((completed / total_lessons) * 100, 2)

        self.last_activity_at = timezone.now()
        self.save(update_fields=['completed_lessons_count', 'progress_percentage', 'last_activity_at'])


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

    completion_data = models.JSONField(
        'Данные завершения',
        null=True,
        blank=True,
        help_text='Дополнительные данные о завершении урока'
    )

    available_at = models.DateTimeField(
        'Доступен с',
        null=True,
        blank=True,
        help_text='Когда урок станет доступен (с учетом задержки)'
    )

    class Meta:
        verbose_name = 'Прогресс по уроку'
        verbose_name_plural = 'Прогресс по урокам'
        db_table = 'lesson_progress'
        unique_together = [['user', 'lesson']]
        ordering = ['lesson__module', 'lesson__order']  # ← ИСПРАВЛЕНО

    def __str__(self):
        status = "Завершен" if self.is_completed else "В процессе"
        return f"{self.user.get_full_name()} - {self.lesson.title} ({status})"

    def save(self, *args, **kwargs):
        """При отметке как завершенный - сохранить дату завершения"""
        if self.is_completed and not self.completed_at:
            self.completed_at = timezone.now()
        super().save(*args, **kwargs)

    def is_accessible(self):
        """Проверить, доступен ли урок сейчас"""
        if not self.available_at:
            return True
        return timezone.now() >= self.available_at

    def mark_completed(self, data=None):
        """
        Отметить урок как завершенный

        Args:
            data: dict - дополнительные данные о завершении
        """
        if not self.is_completed:
            self.is_completed = True
            self.completed_at = timezone.now()
            self.completion_data = data or {}
            self.save()

            # Обновить прогресс по курсу
            enrollment = CourseEnrollment.objects.filter(
                user=self.user,
                course=self.lesson.module.course  # ← ИСПРАВЛЕНО: через module
            ).first()

            if enrollment:
                enrollment.update_progress()


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