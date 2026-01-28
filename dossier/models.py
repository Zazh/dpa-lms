from django.conf import settings
from django.db import models


class StudentDossier(models.Model):
    """
    Досье студента-выпускника.
    Создается при выпуске, защищено от удаления User.
    """

    # === ССЫЛКИ (могут стать NULL при удалении) ===
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='student_dossiers',
        verbose_name='Пользователь'
    )

    graduate = models.OneToOneField(
        'graduates.Graduate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dossier',
        verbose_name='Запись о выпуске'
    )

    # === ЛИЧНЫЕ ДАННЫЕ (копия, защищена) ===
    first_name = models.CharField('Имя', max_length=100)
    last_name = models.CharField('Фамилия', max_length=100)
    middle_name = models.CharField('Отчество', max_length=100, blank=True)
    email = models.EmailField('Email')
    iin = models.CharField('ИИН', max_length=12)
    phone = models.CharField('Телефон', max_length=20, blank=True)

    # === ОБУЧЕНИЕ ===
    course_title = models.CharField('Название курса', max_length=255)
    course_label = models.CharField('Код курса', max_length=50, blank=True)
    group_name = models.CharField('Название группы', max_length=255)
    instructor_name = models.CharField('ФИО инструктора', max_length=255, blank=True)
    instructor_email = models.EmailField('Email инструктора', blank=True)

    # === СЕРТИФИКАТ ===
    certificate_number = models.CharField(
        'Номер сертификата',
        max_length=50,
        unique=True,
        db_index=True
    )

    # === ДАТЫ ===
    enrolled_at = models.DateTimeField('Дата зачисления')
    completed_at = models.DateTimeField('Дата завершения обучения')
    graduated_at = models.DateTimeField('Дата выпуска')
    dossier_created_at = models.DateTimeField('Досье создано', auto_now_add=True)

    # === РЕЗУЛЬТАТЫ ===
    final_score = models.DecimalField(
        'Итоговая оценка (%)',
        max_digits=5,
        decimal_places=2
    )
    total_lessons_completed = models.PositiveIntegerField('Уроков завершено')
    total_study_days = models.PositiveIntegerField('Дней на обучение')
    average_quiz_score = models.DecimalField(
        'Средний балл за тесты (%)',
        max_digits=5,
        decimal_places=2
    )

    # === JSON АРХИВЫ ===
    lessons_history = models.JSONField(
        'История уроков',
        default=list,
        help_text='Все пройденные уроки с датами'
    )

    quizzes_history = models.JSONField(
        'История тестов',
        default=list,
        help_text='Все попытки тестов с ответами'
    )

    assignments_history = models.JSONField(
        'История ДЗ',
        default=list,
        help_text='Все ДЗ с оценками и feedback'
    )

    modules_history = models.JSONField(
        'История модулей',
        default=list,
        help_text='Даты завершения модулей'
    )

    class Meta:
        verbose_name = 'Досье студента'
        verbose_name_plural = 'Досье студентов'
        ordering = ['-graduated_at']
        indexes = [
            models.Index(fields=['certificate_number']),
            models.Index(fields=['iin']),
            models.Index(fields=['email']),
            models.Index(fields=['-graduated_at']),
        ]

    def __str__(self):
        return f"📋 {self.last_name} {self.first_name} - {self.course_title} ({self.certificate_number})"

    def get_full_name(self):
        """Полное ФИО"""
        parts = [self.last_name, self.first_name]
        if self.middle_name:
            parts.append(self.middle_name)
        return ' '.join(parts)


class InstructorDossier(models.Model):
    """
    Досье инструктора.
    Создается при назначении роли, обновляется периодически.
    """

    # === ССЫЛКА ===
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='instructor_dossier',
        verbose_name='Пользователь'
    )

    # === ЛИЧНЫЕ ДАННЫЕ (копия) ===
    first_name = models.CharField('Имя', max_length=100)
    last_name = models.CharField('Фамилия', max_length=100)
    middle_name = models.CharField('Отчество', max_length=100, blank=True)
    email = models.EmailField('Email')
    phone = models.CharField('Телефон', max_length=20, blank=True)

    # === РОЛЬ ===
    role = models.CharField('Роль', max_length=50)
    role_assigned_at = models.DateTimeField('Роль назначена', null=True, blank=True)

    # === СТАТИСТИКА ===
    total_groups_led = models.PositiveIntegerField('Групп вел', default=0)
    total_students_taught = models.PositiveIntegerField('Студентов обучил', default=0)
    total_graduates = models.PositiveIntegerField('Выпустил студентов', default=0)

    total_assignments_reviewed = models.PositiveIntegerField('ДЗ проверено', default=0)
    total_assignments_passed = models.PositiveIntegerField('ДЗ зачтено', default=0)
    total_assignments_rejected = models.PositiveIntegerField('ДЗ на доработку', default=0)

    average_score_given = models.DecimalField(
        'Средняя оценка',
        max_digits=5,
        decimal_places=2,
        default=0
    )

    # === ДАТЫ ===
    registered_at = models.DateTimeField('Дата регистрации')
    dossier_created_at = models.DateTimeField('Досье создано', auto_now_add=True)
    last_updated_at = models.DateTimeField('Последнее обновление', auto_now=True)

    # === JSON АРХИВЫ ===
    groups_history = models.JSONField(
        'История групп',
        default=list,
        help_text='Все группы которые вел'
    )

    reviews_summary = models.JSONField(
        'Сводка проверок',
        default=dict,
        help_text='Статистика по проверкам ДЗ'
    )

    class Meta:
        verbose_name = 'Досье инструктора'
        verbose_name_plural = 'Досье инструкторов'
        ordering = ['-dossier_created_at']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['-total_graduates']),
        ]

    def __str__(self):
        return f"👨‍🏫 {self.last_name} {self.first_name} ({self.role})"

    def get_full_name(self):
        """Полное ФИО"""
        parts = [self.last_name, self.first_name]
        if self.middle_name:
            parts.append(self.middle_name)
        return ' '.join(parts)