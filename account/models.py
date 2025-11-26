from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
import uuid
from datetime import timedelta


class UserManager(BaseUserManager):
    """Менеджер для кастомной модели пользователя"""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email обязателен')

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, iin, first_name, last_name, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_verified', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser должен иметь is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser должен иметь is_superuser=True.')

        # Передаём обязательные поля
        extra_fields['iin'] = iin
        extra_fields['first_name'] = first_name
        extra_fields['last_name'] = last_name

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Кастомная модель пользователя"""

    email = models.EmailField('Email', unique=True, db_index=True)
    iin = models.CharField('ИИН', max_length=12, unique=True, db_index=True)

    first_name = models.CharField('Имя', max_length=150)
    last_name = models.CharField('Фамилия', max_length=150)
    middle_name = models.CharField('Отчество', max_length=150, blank=True, null=True)

    phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        unique=True,
        verbose_name='Телефон'
    )

    # ← ДОБАВИТЬ: Роль пользователя
    ROLE_CHOICES = [
        ('student', 'Студент'),
        ('instructor', 'Инструктор'),
        ('super_instructor', 'Супер-инструктор'),
        ('manager', 'Менеджер'),
        ('super_manager', 'Супер-менеджер'),
    ]

    role = models.CharField(
        'Роль',
        max_length=50,
        choices=ROLE_CHOICES,
        default='student',
        db_index=True,
        help_text='Роль пользователя в системе'
    )

    # ← ДОБАВИТЬ: Для инструкторов - назначенные группы
    assigned_groups = models.ManyToManyField(
        'groups.Group',
        blank=True,
        related_name='assigned_instructors',
        verbose_name='Назначенные группы',
        help_text='Группы, к которым у инструктора есть доступ'
    )

    is_active = models.BooleanField('Активен', default=True)
    is_staff = models.BooleanField('Сотрудник', default=False)
    is_verified = models.BooleanField('Email подтвержден', default=False)

    date_joined = models.DateTimeField('Дата регистрации', default=timezone.now)
    last_login = models.DateTimeField('Последний вход', blank=True, null=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['iin', 'first_name', 'last_name']

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        db_table = 'users'
        ordering = ['-date_joined']

    def __str__(self):
        return self.email

    def get_full_name(self):
        """Возвращает полное имя пользователя"""
        if self.middle_name:
            return f"{self.last_name} {self.first_name} {self.middle_name}"
        return f"{self.last_name} {self.first_name}"

    def get_short_name(self):
        """Возвращает короткое имя пользователя"""
        return self.first_name

    # ← ДОБАВИТЬ: Методы для проверки ролей
    def is_instructor(self):
        """Является ли пользователь инструктором (любого уровня)"""
        return self.role in ['instructor', 'super_instructor']

    def is_super_instructor(self):
        """Является ли супер-инструктором (доступ ко всем группам)"""
        return self.role == 'super_instructor'

    def is_manager(self):
        """Является ли менеджером (любого уровня)"""
        return self.role in ['manager', 'super_manager']

    def is_super_manager(self):
        """Является ли супер-менеджером"""
        return self.role == 'super_manager'

    def is_backoffice_user(self):
        """Имеет ли доступ к backoffice (любая роль кроме студента)"""
        return self.role != 'student'

    def get_accessible_groups(self):
        """
        Получить группы, к которым у пользователя есть доступ
        - Супер-инструктор: все активные группы
        - Инструктор: только назначенные группы
        """
        from groups.models import Group

        if self.is_super_instructor():
            return Group.objects.filter(is_active=True)
        elif self.is_instructor():
            return self.assigned_groups.filter(is_active=True)
        else:
            return Group.objects.none()


# Остальные модели без изменений
class EmailVerificationToken(models.Model):
    """Токен для подтверждения email и установки пароля"""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='verification_tokens')
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Токен подтверждения email'
        verbose_name_plural = 'Токены подтверждения email'
        db_table = 'email_verification_tokens'

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)

    def is_valid(self):
        """Проверка валидности токена"""
        return not self.is_used and timezone.now() < self.expires_at

    def __str__(self):
        return f"Token for {self.user.email}"


class PasswordResetToken(models.Model):
    """Токен для сброса пароля"""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_reset_tokens')
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Токен сброса пароля'
        verbose_name_plural = 'Токены сброса пароля'
        db_table = 'password_reset_tokens'

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=1)
        super().save(*args, **kwargs)

    def is_valid(self):
        """Проверка валидности токена"""
        return not self.is_used and timezone.now() < self.expires_at

    def __str__(self):
        return f"Password reset token for {self.user.email}"