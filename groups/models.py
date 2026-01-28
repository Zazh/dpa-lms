import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from content.models import Course


class Group(models.Model):
    """Группа студентов для курса"""

    DEADLINE_TYPE_CHOICES = [
        ('personal_days', 'Персональные дни'),
        ('fixed_date', 'Фиксированная дата'),
    ]

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='groups',
        verbose_name='Курс'
    )

    name = models.CharField('Название группы', max_length=255)
    description = models.TextField('Описание', blank=True)

    # Реферальная ссылка
    referral_token = models.UUIDField(
        'Реферальный токен',
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        help_text='Уникальная ссылка для приглашения в группу'
    )

    # Типы групп
    is_default = models.BooleanField(
        'Дефолтная группа',
        default=False,
        db_index=True,
        help_text='Группа для самооплаты курса (B2C, одна на курс)'
    )

    is_paid = models.BooleanField(
        'Платная группа',
        default=True,
        help_text='Требуется оплата для доступа'
    )

    # Дедлайны
    deadline_type = models.CharField(
        'Тип дедлайна',
        max_length=20,
        choices=DEADLINE_TYPE_CHOICES,
        default='personal_days',
        help_text='Персональные дни (B2C) или фиксированная дата (B2B)'
    )

    deadline_days = models.PositiveIntegerField(
        'Дедлайн в днях',
        default=90,
        help_text='Для дефолтных групп (B2C): количество дней на обучение'
    )

    deadline_date = models.DateTimeField(
        'Фиксированная дата дедлайна',
        null=True,
        blank=True,
        db_index=True,
        help_text='Для B2B групп: общий дедлайн для всех студентов'
    )

    # Ограничения
    max_students = models.PositiveIntegerField(
        'Максимум студентов',
        default=0,
        help_text='0 = без ограничения'
    )

    is_active = models.BooleanField('Активна', default=True, db_index=True)

    created_at = models.DateTimeField('Создана', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлена', auto_now=True)

    class Meta:
        verbose_name = 'Группа'
        verbose_name_plural = 'Группы'
        ordering = ['course', '-is_default', 'name']
        indexes = [
            models.Index(fields=['course', 'is_active']),
            models.Index(fields=['course', 'is_default']),
            models.Index(fields=['referral_token']),
            models.Index(fields=['deadline_date']),
        ]

    def __str__(self):
        badges = []
        if self.is_default:
            badges.append('B2C')
        else:
            badges.append('B2B')
        badge_str = f' [{"/".join(badges)}]' if badges else ''
        return f"{self.course.title} - {self.name}{badge_str}"

    def get_students_count(self):
        """Текущее количество АКТИВНЫХ студентов в группе"""
        return self.memberships.filter(is_active=True).count()

    def get_instructors_count(self):
        """Количество инструкторов в группе"""
        return self.instructors.filter(is_active=True).count()

    def is_full(self):
        """Проверка заполненности группы"""
        if self.max_students == 0:
            return False
        return self.get_students_count() >= self.max_students

    def calculate_personal_deadline(self):
        """Рассчитать персональный дедлайн для нового студента"""
        if self.deadline_type == 'fixed_date':
            # B2B группа - общая дата для всех
            return self.deadline_date
        else:
            # Дефолтная группа - персональные дни
            if self.deadline_days > 0:
                return timezone.now() + timezone.timedelta(days=self.deadline_days)
            return None  # Бессрочно

    def add_student(self, user, enrolled_via_referral=False):
        """Добавить студента в группу"""
        # Проверка лимита
        if self.is_full():
            return False, 'Группа заполнена'

        # Проверка существующего членства
        existing = GroupMembership.objects.filter(
            group=self,
            user=user,
            is_active=True
        ).exists()

        if existing:
            return False, 'Студент уже в группе'

        # Рассчитываем дедлайн
        personal_deadline = self.calculate_personal_deadline()

        # Создание членства
        GroupMembership.objects.create(
            group=self,
            user=user,
            is_active=True,
            enrolled_via_referral=enrolled_via_referral,
            personal_deadline_at=personal_deadline
        )

        return True, 'Студент добавлен'

    def remove_student(self, user):
        """Удалить студента из группы"""
        memberships = GroupMembership.objects.filter(
            group=self,
            user=user,
            is_active=True
        )

        if not memberships.exists():
            return False, 'Студент не в группе'

        for membership in memberships:
            membership.is_active = False
            membership.left_at = timezone.now()
            membership.save()

            # Синхронизируем статус зачисления
            from progress.models import CourseEnrollment
            try:
                enrollment = CourseEnrollment.objects.get(
                    user=user,
                    course=self.course
                )
                enrollment.sync_active_status()
            except CourseEnrollment.DoesNotExist:
                pass

        return True, 'Студент удален'

    def get_available_slots(self):
        """Количество свободных мест"""
        if self.max_students == 0:
            return '∞'
        return max(0, self.max_students - self.get_students_count())

    def get_referral_link(self):
        """Получить реферальную ссылку"""
        from django.conf import settings
        return f"{settings.FRONTEND_URL}/join/{self.referral_token}"

    def get_deadline_display(self):
        """Отображение дедлайна"""
        if self.deadline_type == 'fixed_date' and self.deadline_date:
            return f"📅 {self.deadline_date.strftime('%d.%m.%Y')}"
        elif self.deadline_days > 0:
            return f"⏰ {self.deadline_days} дн. (персон.)"
        return '∞ Бессрочно'

    @classmethod
    def deactivate_expired_memberships(cls):
        """
        Деактивировать членства с истекшим дедлайном.
        Вызывается периодической задачей.
        """
        from progress.models import CourseEnrollment

        now = timezone.now()
        deactivated_count = 0

        # Находим истекшие членства
        expired_memberships = GroupMembership.objects.filter(
            is_active=True,
            personal_deadline_at__isnull=False,
            personal_deadline_at__lt=now
        )

        for membership in expired_memberships:
            # Деактивируем членство
            membership.is_active = False
            membership.left_at = now
            membership.save()

            # Синхронизируем зачисление
            try:
                enrollment = CourseEnrollment.objects.get(
                    user=membership.user,
                    course=membership.group.course
                )
                enrollment.sync_active_status()
            except CourseEnrollment.DoesNotExist:
                pass

            deactivated_count += 1

        return deactivated_count

class GroupMembership(models.Model):
    """Членство студента в группе"""

    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='memberships',
        verbose_name='Группа'
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='group_memberships',
        verbose_name='Студент'
    )

    is_active = models.BooleanField('Активно', default=True, db_index=True)

    enrolled_via_referral = models.BooleanField(
        'Через реферальную ссылку',
        default=False,
        help_text='Пользователь зашел по реферальной ссылке группы'
    )

    personal_deadline_at = models.DateTimeField(
        'Персональный дедлайн',
        null=True,
        blank=True,
        db_index=True,
        help_text='Индивидуальный дедлайн для этого студента'
    )

    joined_at = models.DateTimeField('Дата вступления', auto_now_add=True, db_index=True)
    left_at = models.DateTimeField('Дата выхода', null=True, blank=True)

    class Meta:
        verbose_name = 'Членство в группе'
        verbose_name_plural = 'Членства в группах'
        ordering = ['-joined_at']
        indexes = [
            models.Index(fields=['group', 'is_active']),
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['personal_deadline_at']),
        ]

    def __str__(self):
        status = '✅' if self.is_active else '❌'
        return f"{status} {self.user.get_full_name()} → {self.group.name}"

    def get_duration_days(self):
        """Длительность членства в днях"""
        if self.is_active:
            duration = timezone.now() - self.joined_at
        else:
            if self.left_at:
                duration = self.left_at - self.joined_at
            else:
                return 0
        return duration.days

    def get_days_until_deadline(self):
        """Дней до дедлайна"""
        if not self.personal_deadline_at:
            return None

        if not self.is_active:
            return 0

        delta = self.personal_deadline_at - timezone.now()
        return max(0, delta.days)

    def is_deadline_soon(self, days=7):
        """Скоро истекает дедлайн?"""
        days_left = self.get_days_until_deadline()
        if days_left is None:
            return False
        return 0 < days_left <= days


class GroupInstructor(models.Model):
    """Инструктор группы с правами доступа"""

    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='instructors',
        verbose_name='Группа'
    )

    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='instructor_groups',
        verbose_name='Инструктор'
    )

    is_active = models.BooleanField('Активен', default=True, db_index=True)

    can_grade = models.BooleanField(
        'Может проверять задания',
        default=True,
        help_text='Проверка домашних заданий и тестов'
    )

    can_view_progress = models.BooleanField(
        'Может видеть прогресс',
        default=True,
        help_text='Просмотр прогресса студентов'
    )

    assigned_at = models.DateTimeField('Дата назначения', auto_now_add=True)

    class Meta:
        verbose_name = 'Инструктор группы'
        verbose_name_plural = 'Инструкторы групп'
        ordering = ['group', '-assigned_at']
        indexes = [
            models.Index(fields=['group', 'is_active']),
            models.Index(fields=['instructor', 'is_active']),
        ]
        unique_together = [['group', 'instructor']]

    def __str__(self):
        status = '✅' if self.is_active else '❌'
        return f"{status} {self.instructor.get_full_name()} → {self.group.name}"

    def get_permissions_display(self):
        """Отображение прав"""
        permissions = []
        if self.can_grade:
            permissions.append('✅ Проверка')
        if self.can_view_progress:
            permissions.append('📊 Прогресс')
        return ' | '.join(permissions) if permissions else '❌ Нет прав'