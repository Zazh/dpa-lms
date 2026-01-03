from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from content.models import Lesson


class AssignmentLesson(models.Model):
    """Настройки домашнего задания (расширение Lesson)"""

    lesson = models.OneToOneField(
        Lesson,
        on_delete=models.CASCADE,
        related_name='assignmentlesson',
        verbose_name='Урок'
    )

    instructions = models.TextField(
        'Инструкции',
        help_text='Что нужно сделать для выполнения задания'
    )

    require_text = models.BooleanField(
        'Требуется текстовый ответ',
        default=True
    )

    require_file = models.BooleanField(
        'Требуется файл',
        default=False
    )

    max_score = models.PositiveIntegerField(
        'Максимальный балл',
        default=100,
        validators=[MinValueValidator(1)]
    )

    deadline_days = models.PositiveIntegerField(
        'Дедлайн (дни)',
        default=7,
        help_text='Количество дней на выполнение после открытия урока'
    )

    allow_late_submission = models.BooleanField(
        'Разрешить сдачу после дедлайна',
        default=True
    )

    allow_resubmission = models.BooleanField(
        'Разрешить пересдачу',
        default=True,
        help_text='Студент может сдать повторно после "Требуется доработка"'
    )

    class Meta:
        verbose_name = 'Домашнее задание'
        verbose_name_plural = 'Домашние задания'

    def __str__(self):
        return f"Задание: {self.lesson.title}"

    def get_submissions_count(self):
        """Количество сданных работ"""
        return self.submissions.count()

    def get_pending_count(self):
        """Количество работ на проверке"""
        return self.submissions.filter(status='in_review').count()

    def get_average_score(self):
        """Средний балл по заданию"""
        submissions = self.submissions.filter(status='passed', score__isnull=False)
        if submissions.exists():
            avg = submissions.aggregate(models.Avg('score'))['score__avg']
            return round(avg, 2) if avg else 0
        return 0


class AssignmentSubmission(models.Model):
    """Сдача домашнего задания"""

    STATUS_CHOICES = [
        ('waiting', '⏳ Ожидает сдачи'),
        ('in_review', '🔍 На проверке'),
        ('needs_revision', '✏️ Требуется доработка'),
        ('failed', '❌ Не зачтено'),
        ('passed', '✅ Зачтено'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='assignment_submissions',
        verbose_name='Студент'
    )

    assignment = models.ForeignKey(
        AssignmentLesson,
        on_delete=models.CASCADE,
        related_name='submissions',
        verbose_name='Задание'
    )

    submission_number = models.PositiveIntegerField(
        'Номер попытки',
        default=1
    )

    submission_text = models.TextField(
        'Текст ответа',
        blank=True
    )

    submission_file = models.FileField(
        'Файл',
        upload_to='assignment_submissions/%Y/%m/',
        blank=True,
        null=True
    )

    status = models.CharField(
        'Статус',
        max_length=20,
        choices=STATUS_CHOICES,
        default='in_review',
        db_index=True
    )

    score = models.PositiveIntegerField(
        'Балл',
        null=True,
        blank=True,
        help_text='Балл за выполнение задания'
    )

    feedback = models.TextField(
        'Обратная связь от преподавателя',
        blank=True
    )

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_assignments',
        verbose_name='Проверил'
    )

    submitted_at = models.DateTimeField('Дата сдачи', auto_now_add=True, db_index=True)
    reviewed_at = models.DateTimeField('Дата проверки', null=True, blank=True)

    class Meta:
        verbose_name = 'Сдача задания'
        verbose_name_plural = 'Сдачи заданий'
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['user', 'assignment', '-submitted_at']),
            models.Index(fields=['status', '-submitted_at']),
            models.Index(fields=['assignment', 'status']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.assignment.lesson.title} (#{self.submission_number})"

    def save(self, *args, **kwargs):
        """Переопределяем save для автозавершения урока"""
        if self.pk:
            try:
                old_submission = AssignmentSubmission.objects.get(pk=self.pk)
                if old_submission.status != 'passed' and self.status == 'passed':
                    # Статус изменен на passed — завершаем урок через mark_completed
                    super().save(*args, **kwargs)

                    from progress.models import LessonProgress

                    lesson_progress, created = LessonProgress.objects.get_or_create(
                        user=self.user,
                        lesson=self.assignment.lesson,
                        defaults={'is_completed': False}
                    )

                    if not lesson_progress.is_completed:
                        lesson_progress.mark_completed(
                            completion_data={'assignment_score': self.score}
                        )
                    return
            except AssignmentSubmission.DoesNotExist:
                pass

        super().save(*args, **kwargs)

    def mark_in_review(self, instructor):
        """Взять на проверку"""
        self.status = 'in_review'
        self.reviewed_by = instructor
        self.save()

    def mark_needs_revision(self, instructor, feedback):
        """Отправить на доработку"""
        self.status = 'needs_revision'
        self.reviewed_by = instructor
        self.feedback = feedback
        self.reviewed_at = timezone.now()
        self.save()


        from notifications.services import NotificationService
        NotificationService.notify_homework_needs_revision(
            user=self.user,
            assignment_submission=self
        )

    def mark_failed(self, instructor, feedback, score=0):
        """Не зачесть"""
        self.status = 'failed'
        self.score = score
        self.reviewed_by = instructor
        self.feedback = feedback
        self.reviewed_at = timezone.now()
        self.save()

    def mark_passed(self, instructor, score, feedback=''):
        """Зачесть"""
        self.status = 'passed'
        self.score = score
        self.reviewed_by = instructor
        self.feedback = feedback
        self.reviewed_at = timezone.now()
        self.save()

        # Обновить прогресс урока
        from progress.models import LessonProgress, CourseEnrollment

        lesson_progress, created = LessonProgress.objects.get_or_create(
            user=self.user,
            lesson=self.assignment.lesson,
            defaults={'is_completed': False}
        )

        # Вызываем mark_completed — он пересчитает прогресс курса и создаст выпускника
        if not lesson_progress.is_completed:
            lesson_progress.mark_completed(completion_data={'assignment_score': score})

        # Уведомление
        from notifications.services import NotificationService
        NotificationService.notify_homework_accepted(
            user=self.user,
            assignment_submission=self
        )

    def get_score_percentage(self):
        """Процент от максимального балла"""
        if self.score is not None and self.assignment.max_score > 0:
            return round((self.score / self.assignment.max_score) * 100, 2)
        return 0

    def is_late(self):
        """Проверка, сдано ли после дедлайна"""
        # TODO: Реализовать после создания LessonProgress
        return False

    def get_comments_count(self):
        """Количество комментариев"""
        return self.comments.count()

    def get_unread_comments_count(self, user):
        """Количество непрочитанных комментариев для пользователя"""
        return self.comments.filter(is_read=False).exclude(author=user).count()


class AssignmentComment(models.Model):
    """Комментарий к сдаче задания"""

    submission = models.ForeignKey(
        AssignmentSubmission,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name='Сдача'
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='assignment_comments',
        verbose_name='Автор'
    )

    message = models.TextField('Сообщение')

    is_instructor = models.BooleanField(
        'От преподавателя',
        default=False,
        db_index=True
    )

    is_read = models.BooleanField(
        'Прочитано',
        default=False
    )

    created_at = models.DateTimeField('Создан', auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Комментарий'
        verbose_name_plural = 'Комментарии'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['submission', 'created_at']),
        ]

    def __str__(self):
        author_type = '👨‍🏫' if self.is_instructor else '👨‍🎓'
        return f"{author_type} {self.author.email} - {self.created_at.strftime('%d.%m.%Y %H:%M')}"