from django.db import models
from django.conf import settings
from django.utils import timezone
from content.models import Course
from groups.models import Group


class Graduate(models.Model):
    """Выпускник курса"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='graduations',
        verbose_name='Студент'
    )

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='graduates',
        verbose_name='Курс'
    )

    group = models.ForeignKey(
        Group,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='graduates',
        verbose_name='Группа',
        help_text='Из какой группы выпустился'
    )

    # Дата и результаты
    graduated_at = models.DateTimeField('Дата выпуска', auto_now_add=True, db_index=True)

    final_score = models.DecimalField(
        'Итоговая оценка (%)',
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text='Средний балл по всем тестам и заданиям'
    )

    # Статистика обучения
    total_lessons_completed = models.PositiveIntegerField(
        'Уроков завершено',
        default=0
    )

    average_quiz_score = models.DecimalField(
        'Средний балл за тесты',
        max_digits=5,
        decimal_places=2,
        default=0
    )

    total_study_days = models.PositiveIntegerField(
        'Дней на обучение',
        default=0,
        help_text='От зачисления до завершения'
    )

    # Сертификат
    certificate_number = models.CharField(
        'Номер сертификата',
        max_length=50,
        unique=True,
        blank=True,
        null=True,
        db_index=True
    )

    certificate_file = models.FileField(
        'Файл сертификата',
        upload_to='certificates/%Y/%m/',
        blank=True,
        null=True
    )

    certificate_issued_at = models.DateTimeField(
        'Дата выдачи сертификата',
        null=True,
        blank=True
    )

    # Дополнительно
    notes = models.TextField('Примечания', blank=True)

    class Meta:
        verbose_name = 'Выпускник'
        verbose_name_plural = 'Выпускники'
        ordering = ['-graduated_at']
        unique_together = [['user', 'course']]  # Один диплом на курс
        indexes = [
            models.Index(fields=['user', 'course']),
            models.Index(fields=['course', '-graduated_at']),
            models.Index(fields=['certificate_number']),
        ]

    def __str__(self):
        return f"🎓 {self.user.get_full_name()} - {self.course.title}"

    def generate_certificate_number(self):
        """Генерация уникального номера сертификата"""
        if not self.certificate_number:
            import uuid
            year = self.graduated_at.year
            unique_id = str(uuid.uuid4())[:8].upper()
            self.certificate_number = f"CERT-{year}-{unique_id}"
            self.save()
        return self.certificate_number

    def issue_certificate(self):
        """Выдать сертификат"""
        if not self.certificate_issued_at:
            self.generate_certificate_number()
            self.certificate_issued_at = timezone.now()
            self.save()

            # TODO: Здесь будет генерация PDF сертификата
            # from certificates.services import CertificateGenerator
            # generator = CertificateGenerator()
            # self.certificate_file = generator.generate(self)
            # self.save()

    def get_certificate_status(self):
        """Статус сертификата"""
        if self.certificate_issued_at:
            return 'issued'  # Выдан
        return 'pending'  # Ожидает выдачи

    @classmethod
    def create_from_enrollment(cls, enrollment):
        """Создать выпускника из зачисления"""
        from quizzes.models import QuizAttempt
        from django.db.models import Avg

        # Проверяем, не создан ли уже
        if cls.objects.filter(user=enrollment.user, course=enrollment.course).exists():
            return None

        # Рассчитываем средний балл за тесты
        quiz_attempts = QuizAttempt.objects.filter(
            user=enrollment.user,
            quiz__lesson__module__course=enrollment.course,
            status='completed'
        )

        avg_quiz_score = quiz_attempts.aggregate(
            Avg('score_percentage')
        )['score_percentage__avg'] or 0

        # Рассчитываем длительность обучения
        study_duration = (timezone.now() - enrollment.enrolled_at).days

        # Создаем выпускника
        graduate = cls.objects.create(
            user=enrollment.user,
            course=enrollment.course,
            group=enrollment.group,
            final_score=enrollment.progress_percentage,
            total_lessons_completed=enrollment.completed_lessons_count,
            average_quiz_score=avg_quiz_score,
            total_study_days=study_duration
        )

        return graduate


class GraduateAchievement(models.Model):
    """Достижения выпускника"""

    ACHIEVEMENT_TYPES = [
        ('perfect_score', '💯 Идеальный результат'),
        ('fast_learner', '⚡ Быстрое обучение'),
        ('best_student', '🏆 Лучший студент'),
        ('helpful', '🤝 Помощь другим'),
        ('active', '🔥 Активный студент'),
    ]

    graduate = models.ForeignKey(
        Graduate,
        on_delete=models.CASCADE,
        related_name='achievements',
        verbose_name='Выпускник'
    )

    achievement_type = models.CharField(
        'Тип достижения',
        max_length=50,
        choices=ACHIEVEMENT_TYPES
    )

    description = models.TextField('Описание', blank=True)
    earned_at = models.DateTimeField('Получено', auto_now_add=True)

    class Meta:
        verbose_name = 'Достижение'
        verbose_name_plural = 'Достижения'
        ordering = ['-earned_at']
        unique_together = [['graduate', 'achievement_type']]

    def __str__(self):
        return f"{self.get_achievement_type_display()} - {self.graduate.user.get_full_name()}"