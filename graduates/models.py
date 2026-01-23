from django.db import models
from django.conf import settings
from django.utils import timezone
from content.models import Course
from groups.models import Group


class Graduate(models.Model):
    """Выпускник курса"""

    # Статусы выпускника
    STATUS_CHOICES = [
        ('pending', '⏳ Закончил обучение (ожидает выпуска)'),
        ('graduated', '🎓 Выпущен'),
        ('rejected', '❌ Отклонен'),
    ]

    # === ОСНОВНАЯ ИНФОРМАЦИЯ ===
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
        help_text='Группа в которой проходил обучение'
    )

    # === СТАТУС И ДАТЫ ===
    status = models.CharField(
        'Статус',
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True
    )

    completed_at = models.DateTimeField(
        'Дата завершения обучения',
        default=timezone.now,
        db_index=True,
        help_text='Когда достиг 100% прогресса'
    )

    graduated_at = models.DateTimeField(
        'Дата выпуска',
        null=True,
        blank=True,
        db_index=True,
        help_text='Когда менеджер подтвердил выпуск'
    )

    graduated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='graduated_students',
        verbose_name='Выпустил (менеджер)'
    )

    # === РЕЗУЛЬТАТЫ ОБУЧЕНИЯ ===
    final_score = models.DecimalField(
        'Итоговая оценка (%)',
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text='Средний балл по всем тестам'
    )

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

    # === ДЕТАЛИ ПРОХОЖДЕНИЯ ===
    completion_details = models.JSONField(
        'Детали прохождения',
        default=dict,
        blank=True,
        help_text='Даты прохождения модулей, уроков, попытки тестов'
    )

    # === СЕРТИФИКАТ ===
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

    # === ДОПОЛНИТЕЛЬНО ===
    notes = models.TextField('Примечания менеджера', blank=True)

    class Meta:
        verbose_name = 'Выпускник'
        verbose_name_plural = 'Выпускники'
        ordering = ['-completed_at']
        unique_together = [['user', 'course']]
        indexes = [
            models.Index(fields=['user', 'course']),
            models.Index(fields=['status', '-completed_at']),
            models.Index(fields=['group', 'status']),
            models.Index(fields=['certificate_number']),
        ]

    def __str__(self):
        status_icon = {
            'pending': '⏳',
            'graduated': '🎓',
            'rejected': '❌'
        }.get(self.status, '❓')
        return f"{status_icon} {self.user.get_full_name()} - {self.course.title}"

    # === МЕТОДЫ ===

    def get_instructor(self):
        """Получить инструктора группы"""
        if not self.group:
            return None

        from groups.models import GroupInstructor
        instructor = GroupInstructor.objects.filter(
            group=self.group,
            is_active=True
        ).first()

        return instructor.instructor if instructor else None

    def get_quiz_attempts_summary(self):
        """Сводка по попыткам тестов"""
        from quizzes.models import QuizAttempt

        attempts = QuizAttempt.objects.filter(
            user=self.user,
            quiz__lesson__module__course=self.course,
            status='completed'
        ).select_related('quiz__lesson').order_by('quiz__lesson__order', 'attempt_number')

        summary = []
        for attempt in attempts:
            summary.append({
                'lesson': attempt.quiz.lesson.title,
                'attempt_number': attempt.attempt_number,
                'score': float(attempt.score_percentage),
                'passed': attempt.is_passed(),
                'date': attempt.completed_at.strftime('%d.%m.%Y %H:%M') if attempt.completed_at else '-'
            })

        return summary

    def calculate_completion_details(self):
        """Рассчитать детали прохождения"""
        from progress.models import LessonProgress
        from content.models import Module

        details = {
            'modules': [],
            'lessons': [],
            'quizzes': self.get_quiz_attempts_summary()
        }

        # Модули
        modules = Module.objects.filter(course=self.course).order_by('order')
        for module in modules:
            module_lessons = LessonProgress.objects.filter(
                user=self.user,
                lesson__module=module,
                is_completed=True
            )

            if module_lessons.exists():
                last_completed = module_lessons.order_by('-completed_at').first()
                details['modules'].append({
                    'title': module.title,
                    'order': module.order,
                    'completed_at': last_completed.completed_at.strftime(
                        '%d.%m.%Y %H:%M') if last_completed.completed_at else '-'
                })

        # Уроки
        lessons = LessonProgress.objects.filter(
            user=self.user,
            lesson__module__course=self.course,
            is_completed=True
        ).select_related('lesson', 'lesson__module').order_by('lesson__module__order', 'lesson__order')

        for lesson_progress in lessons:
            details['lessons'].append({
                'module': lesson_progress.lesson.module.title,
                'title': lesson_progress.lesson.title,
                'type': lesson_progress.lesson.get_lesson_type_display(),
                'completed_at': lesson_progress.completed_at.strftime(
                    '%d.%m.%Y %H:%M') if lesson_progress.completed_at else '-'
            })

        return details

    def approve_graduation(self, manager):
        """Подтвердить выпуск (вызывается менеджером)"""
        from django.db import transaction

        if self.status != 'pending':
            return False

        # Всё в одной транзакции — или всё сохранится, или ничего
        with transaction.atomic():
            self.status = 'graduated'
            self.graduated_at = timezone.now()
            self.graduated_by = manager
            self.save()

            # Создаём сертификат
            from certificates.services import CertificateService
            certificate = CertificateService.create_from_graduate(self)
            self.certificate = certificate

            # Создаём досье
            from dossier.services import DossierService
            DossierService.create_student_dossier(self)

        # После успешной транзакции — фоновые задачи
        from certificates.tasks import generate_certificate_pdf
        generate_certificate_pdf.delay(certificate.id)

        # Уведомление студенту
        from notifications.services import NotificationService
        NotificationService.notify_graduation(self.user, self)

        return True

    def reject_graduation(self, manager, reason=''):
        """Отклонить выпуск"""
        if self.status == 'pending':
            self.status = 'rejected'
            self.graduated_by = manager
            if reason:
                self.notes = f"Отклонено: {reason}\n{self.notes}"
            self.save()
            return True
        return False

    @classmethod
    def create_from_enrollment(cls, enrollment):
        """
        Создать выпускника из зачисления (вызывается автоматически при 100%)
        """
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
            status='pending',
            final_score=avg_quiz_score,
            total_lessons_completed=enrollment.completed_lessons_count,
            average_quiz_score=avg_quiz_score,
            total_study_days=study_duration
        )

        # Рассчитываем детали
        graduate.completion_details = graduate.calculate_completion_details()
        graduate.save(update_fields=['completion_details'])

        return graduate