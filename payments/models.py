from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import uuid
import secrets


class CoursePrice(models.Model):
    """Цена курса для онлайн-продажи"""

    course = models.OneToOneField(
        'content.Course',
        on_delete=models.CASCADE,
        related_name='price_settings',
        verbose_name='Курс'
    )

    price = models.DecimalField(
        'Цена',
        max_digits=10,
        decimal_places=2,
        help_text='Цена в тенге'
    )

    is_active = models.BooleanField(
        'Продажи активны',
        default=True,
        db_index=True,
        help_text='Можно ли покупать курс онлайн'
    )

    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Цена курса'
        verbose_name_plural = 'Цены курсов'
        db_table = 'payments_course_price'

    def __str__(self):
        status = '✅' if self.is_active else '❌'
        return f"{status} {self.course.title} — {self.price:,.0f} ₸"


class Order(models.Model):
    """Заказ на покупку курса"""

    STATUS_CHOICES = [
        ('pending', 'Ожидает оплаты'),
        ('paid', 'Оплачен'),
        ('expired', 'Истёк'),
        ('completed', 'Завершён'),
        ('cancelled', 'Отменён'),
    ]

    # Уникальный токен для доступа к заказу
    token = models.CharField(
        'Токен',
        max_length=64,
        unique=True,
        db_index=True,
        editable=False
    )

    # Контакты покупателя (до регистрации)
    email = models.EmailField('Email покупателя')
    phone = models.CharField('Телефон', max_length=20, blank=True)

    # Что покупает
    course = models.ForeignKey(
        'content.Course',
        on_delete=models.PROTECT,
        related_name='orders',
        verbose_name='Курс'
    )

    # Дефолтная группа курса (для зачисления после оплаты)
    group = models.ForeignKey(
        'groups.Group',
        on_delete=models.PROTECT,
        related_name='orders',
        verbose_name='Группа'
    )

    # Сумма заказа (фиксируем на момент создания)
    amount = models.DecimalField(
        'Сумма',
        max_digits=10,
        decimal_places=2
    )

    # Связь с пользователем (заполняется после регистрации/входа)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders',
        verbose_name='Пользователь'
    )

    # Статус заказа
    status = models.CharField(
        'Статус',
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True
    )

    # Kaspi данные
    kaspi_payment_id = models.CharField(
        'Kaspi Payment ID',
        max_length=100,
        blank=True,
        help_text='ID платежа в системе Kaspi'
    )

    kaspi_qr_token = models.CharField(
        'Kaspi QR Token',
        max_length=255,
        blank=True,
        help_text='Токен для генерации QR-кода'
    )

    kaspi_qr_payload = models.TextField(
        'Kaspi QR Payload',
        blank=True,
        help_text='Данные для отображения QR-кода'
    )

    # Временные метки
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    expires_at = models.DateTimeField('Истекает', db_index=True)
    paid_at = models.DateTimeField('Оплачен', null=True, blank=True)
    completed_at = models.DateTimeField('Завершён', null=True, blank=True)

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        db_table = 'payments_order'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'expires_at']),
            models.Index(fields=['email', 'status']),
            models.Index(fields=['kaspi_payment_id']),
        ]

    def __str__(self):
        return f"Заказ #{self.id} — {self.course.title} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        # Генерируем токен при создании
        if not self.token:
            self.token = secrets.token_urlsafe(32)

        # Устанавливаем срок действия (30 минут)
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=30)

        super().save(*args, **kwargs)

    def is_expired(self):
        """Проверка истечения срока"""
        return timezone.now() > self.expires_at

    def get_time_remaining(self):
        """Оставшееся время в секундах"""
        if self.is_expired():
            return 0
        delta = self.expires_at - timezone.now()
        return max(0, int(delta.total_seconds()))

    def mark_as_paid(self, kaspi_payment_id=None):
        """Отметить заказ как оплаченный"""
        self.status = 'paid'
        self.paid_at = timezone.now()
        if kaspi_payment_id:
            self.kaspi_payment_id = kaspi_payment_id
        self.save()

    def mark_as_expired(self):
        """Отметить заказ как истёкший"""
        if self.status == 'pending':
            self.status = 'expired'
            self.save()

    def complete(self, user):
        """
        Завершить заказ: привязать пользователя и зачислить на курс.
        Вызывается после успешной авторизации/регистрации.
        """
        from groups.models import GroupMembership
        if self.status != 'paid':
            return False, 'Заказ не оплачен'

        if self.status == 'completed':
            return False, 'Заказ уже завершён'

        # Привязываем пользователя
        self.user = user
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()

        # Добавляем в группу
        # CourseEnrollment и LessonProgress создаются автоматически
        # через сигнал post_save на GroupMembership (groups/signals.py)
        success, message = self.group.add_student(user, enrolled_via_referral=False)

        if not success:
            # Если уже в группе — это нормально, продолжаем
            if 'уже в группе' not in message.lower():
                return False, message

        return True, 'Вы успешно зачислены на курс'

    @classmethod
    def check_existing_enrollment(cls, email, course, group):
        """
        Проверить, есть ли уже зачисление на курс.
        Проверяем по email в дефолтной группе.
        """
        from account.models import User
        from groups.models import GroupMembership

        try:
            user = User.objects.get(email=email)
            # Проверяем членство в этой группе
            return GroupMembership.objects.filter(
                user=user,
                group=group,
                is_active=True
            ).exists()
        except User.DoesNotExist:
            return False

    @classmethod
    def get_pending_orders(cls):
        """Получить все pending заказы, которые ещё не истекли"""
        return cls.objects.filter(
            status='pending',
            expires_at__gt=timezone.now()
        )

    @classmethod
    def expire_old_orders(cls):
        """Пометить истёкшие заказы"""
        expired_count = cls.objects.filter(
            status='pending',
            expires_at__lte=timezone.now()
        ).update(status='expired')
        return expired_count
