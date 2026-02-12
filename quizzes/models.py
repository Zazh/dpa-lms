from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from content.models import Lesson


class QuizLesson(models.Model):
    """Настройки теста (расширение Lesson)"""

    lesson = models.OneToOneField(
        Lesson,
        on_delete=models.CASCADE,
        related_name='quizlesson',
        verbose_name='Урок'
    )

    passing_score = models.PositiveIntegerField(
        'Проходной балл (%)',
        default=70,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text='Минимальный процент для прохождения теста'
    )

    max_attempts = models.PositiveIntegerField(
        'Максимум попыток',
        default=3,
        validators=[MinValueValidator(1)],
        help_text='0 = неограниченно'
    )

    retry_delay_minutes = models.PositiveIntegerField(
        'Задержка между попытками (минуты)',
        default=0,
        help_text='Сколько минут ждать между попытками (0 = без задержки)'
    )

    time_limit_minutes = models.PositiveIntegerField(
        'Ограничение по времени (минуты)',
        default=0,
        help_text='0 = без ограничения'
    )

    show_correct_answers = models.BooleanField(
        'Показывать правильные ответы',
        default=True,
        help_text='После завершения теста'
    )

    shuffle_questions = models.BooleanField(
        'Перемешивать вопросы',
        default=False
    )

    shuffle_answers = models.BooleanField(
        'Перемешивать ответы',
        default=False
    )

    is_final_exam = models.BooleanField(
        'Итоговый тест',
        default=False,
        help_text='Если включено — вопросы агрегируются из промежуточных тестов курса'
    )

    total_questions = models.PositiveIntegerField(
        'Количество вопросов',
        default=20,
        validators=[MinValueValidator(1)],
        help_text='Сколько вопросов включить в итоговый тест'
    )

    questions_per_quiz = models.PositiveIntegerField(
        'Вопросов с каждого теста',
        default=0,
        help_text='0 = равномерно распределить. Иначе — фиксированное количество с каждого теста'
    )

    class Meta:
        verbose_name = 'Тест'
        verbose_name_plural = 'Тесты'

    def __str__(self):
        return f"Тест: {self.lesson.title}"

    def get_questions_count(self):
        """Количество вопросов в тесте"""
        return self.questions.count()

    def get_total_points(self):
        """Общее количество баллов теста"""
        return sum(q.points for q in self.questions.all())

    def can_user_attempt(self, user):
        """Может ли пользователь пройти тест (проверка попыток и задержки)"""
        attempts = self.attempts.filter(user=user).order_by('-started_at')

        # Проверка, что тест уже сдан
        passed_attempts = attempts.filter(
            status='completed',
            score_percentage__gte=self.passing_score
        )
        if passed_attempts.exists():
            return False, 'Тест уже сдан', None

        # Проверка количества попыток
        if self.max_attempts > 0:
            if attempts.count() >= self.max_attempts:
                return False, 'Исчерпан лимит попыток, обратитесь к своему инструктору', None

        # Проверка задержки между попытками
        if self.retry_delay_minutes > 0:
            # Учитываем completed И timeout
            finished_attempts = attempts.filter(
                status__in=['completed', 'timeout'],
                completed_at__isnull=False
            ).order_by('-completed_at')

            if finished_attempts.exists():
                last_attempt = finished_attempts.first()
                available_at = last_attempt.completed_at + timezone.timedelta(minutes=self.retry_delay_minutes)

                if timezone.now() < available_at:
                    remaining = available_at - timezone.now()
                    remaining_minutes = int(remaining.total_seconds() / 60)

                    if remaining_minutes >= 60:
                        hours = remaining_minutes // 60
                        mins = remaining_minutes % 60
                        if mins > 0:
                            message = f'Подождите {hours} ч. {mins} мин.'
                        else:
                            message = f'Подождите {hours} ч.'
                    elif remaining_minutes < 1:
                        message = 'Подождите 1 мин.'
                    else:
                        message = f'Подождите {remaining_minutes} мин.'

                    return False, message, available_at.isoformat()

        return True, 'OK', None


class QuizQuestion(models.Model):
    """Вопрос теста"""

    QUESTION_TYPES = [
        ('single_choice', 'Один правильный ответ'),
        ('multiple_choice', 'Несколько правильных ответов'),
        ('true_false', 'Верно/Неверно'),
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
        default='single_choice'
    )

    question_text = models.TextField('Текст вопроса')
    explanation = models.TextField('Пояснение', blank=True, help_text='Показывается после ответа')

    points = models.PositiveIntegerField(
        'Баллы',
        default=1,
        validators=[MinValueValidator(1)]
    )

    order = models.PositiveIntegerField('Порядок', default=0, db_index=True)

    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлен', auto_now=True)

    class Meta:
        verbose_name = 'Вопрос'
        verbose_name_plural = 'Вопросы'
        ordering = ['quiz', 'order']
        unique_together = ['quiz', 'order']

    def __str__(self):
        return f"{self.quiz.lesson.title} - {self.question_text[:50]}"

    def get_correct_answers_count(self):
        """Количество правильных ответов"""
        return self.answers.filter(is_correct=True).count()

    def get_answers_count(self):
        """Общее количество ответов"""
        return self.answers.count()


class QuizAnswer(models.Model):
    """Вариант ответа на вопрос"""

    question = models.ForeignKey(
        QuizQuestion,
        on_delete=models.CASCADE,
        related_name='answers',
        verbose_name='Вопрос'
    )

    answer_text = models.TextField('Текст ответа')
    is_correct = models.BooleanField('Правильный ответ', default=False, db_index=True)

    order = models.PositiveIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Вариант ответа'
        verbose_name_plural = 'Варианты ответов'
        ordering = ['question', 'order']

    def __str__(self):
        correct = '✅' if self.is_correct else '❌'
        return f"{correct} {self.answer_text[:50]}"


class QuizAttempt(models.Model):
    """Попытка прохождения теста"""

    STATUS_CHOICES = [
        ('in_progress', 'В процессе'),
        ('completed', 'Завершена'),
        ('timeout', 'Время истекло'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='quiz_attempts',
        verbose_name='Пользователь'
    )

    quiz = models.ForeignKey(
        QuizLesson,
        on_delete=models.CASCADE,
        related_name='attempts',
        verbose_name='Тест'
    )

    attempt_number = models.PositiveIntegerField('Номер попытки', default=1)

    status = models.CharField(
        'Статус',
        max_length=20,
        choices=STATUS_CHOICES,
        default='in_progress',
        db_index=True
    )

    score_percentage = models.DecimalField(
        'Результат (%)',
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True
    )

    questions_order = models.JSONField(
        'Порядок вопросов',
        default=list,
        blank=True,
        help_text='Список ID вопросов в порядке показа студенту'
    )

    started_at = models.DateTimeField('Начало', auto_now_add=True, db_index=True)
    completed_at = models.DateTimeField('Завершение', null=True, blank=True)

    class Meta:
        verbose_name = 'Попытка прохождения теста'
        verbose_name_plural = 'Попытки прохождения тестов'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['user', 'quiz', '-started_at']),
            models.Index(fields=['status', '-started_at']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.quiz.lesson.title} (Попытка #{self.attempt_number})"

    def calculate_score(self):
        """Рассчитать результат попытки"""
        responses = self.responses.all()
        if not responses.exists():
            return 0

        total_points = sum(r.question.points for r in responses)
        earned_points = sum(r.points_earned for r in responses)

        if total_points > 0:
            percentage = (earned_points / total_points) * 100
            return round(percentage, 2)
        return 0

    def is_passed(self):
        """Проверка, пройден ли тест"""
        if self.score_percentage is None:
            return False
        return self.score_percentage >= self.quiz.passing_score

    def complete(self):
        """Завершить попытку и рассчитать результат"""
        self.score_percentage = self.calculate_score()
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()

        # Обновить прогресс урока если тест пройден
        if self.is_passed():
            from progress.models import LessonProgress

            # ИСПРАВЛЕНО: Используем mark_completed() для полной логики
            lesson_progress, created = LessonProgress.objects.get_or_create(
                user=self.user,
                lesson=self.quiz.lesson,
                defaults={'is_completed': False}
            )

            lesson_progress.mark_completed({
                'quiz_score': float(self.score_percentage),
                'quiz_attempt': self.attempt_number
            })

    def get_duration_seconds(self):
        """Длительность попытки в секундах"""
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return (timezone.now() - self.started_at).total_seconds()

    def is_time_expired(self):
        """Проверить, истекло ли время на прохождение теста"""
        if self.quiz.time_limit_minutes <= 0:
            return False  # Нет ограничения по времени

        deadline = self.started_at + timezone.timedelta(minutes=self.quiz.time_limit_minutes)
        return timezone.now() > deadline

    def get_time_remaining_seconds(self):
        """Получить оставшееся время в секундах"""
        if self.quiz.time_limit_minutes <= 0:
            return None  # Нет ограничения

        deadline = self.started_at + timezone.timedelta(minutes=self.quiz.time_limit_minutes)
        remaining = deadline - timezone.now()
        return max(0, int(remaining.total_seconds()))

    def complete_as_timeout(self):
        """Завершить попытку по таймауту - ВСЕ ответы считаются неправильными"""
        self.score_percentage = 0  # При таймауте всегда 0%
        self.status = 'timeout'
        self.completed_at = timezone.now()
        self.save()


class QuizResponse(models.Model):
    """Ответ пользователя на вопрос"""

    attempt = models.ForeignKey(
        QuizAttempt,
        on_delete=models.CASCADE,
        related_name='responses',
        verbose_name='Попытка'
    )

    question = models.ForeignKey(
        QuizQuestion,
        on_delete=models.PROTECT,
        related_name='responses',
        verbose_name='Вопрос'
    )

    selected_answers = models.ManyToManyField(
        QuizAnswer,
        related_name='selected_by',
        verbose_name='Выбранные ответы'
    )

    answers_order = models.JSONField(
        'Порядок ответов',
        default=list,
        blank=True,
        help_text='Список ID ответов в порядке показа студенту'
    )

    is_correct = models.BooleanField('Правильно', default=False)
    points_earned = models.PositiveIntegerField('Заработано баллов', default=0)

    answered_at = models.DateTimeField('Время ответа', auto_now_add=True)

    class Meta:
        verbose_name = 'Ответ на вопрос'
        verbose_name_plural = 'Ответы на вопросы'
        ordering = ['attempt', 'question__order']
        unique_together = ['attempt', 'question']

    def __str__(self):
        status = '✅' if self.is_correct else '❌'
        return f"{status} {self.attempt.user.email} - {self.question.question_text[:30]}"

    def check_answer(self):
        """Проверить правильность ответа и начислить баллы"""
        selected = set(self.selected_answers.all())
        correct = set(self.question.answers.filter(is_correct=True))

        # Проверка правильности
        self.is_correct = (selected == correct)

        # Начисление баллов
        if self.is_correct:
            self.points_earned = self.question.points
        else:
            self.points_earned = 0

        self.save()