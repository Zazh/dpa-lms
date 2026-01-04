from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import CoursePrice, Order


@admin.register(CoursePrice)
class CoursePriceAdmin(admin.ModelAdmin):
    list_display = ['course', 'formatted_price', 'is_active', 'updated_at']
    list_filter = ['is_active']
    search_fields = ['course__title']
    list_editable = ['is_active']

    def formatted_price(self, obj):
        return f"{obj.price:,.0f} ₸"
    formatted_price.short_description = 'Цена'


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'email',
        'course',
        'formatted_amount',
        'status_badge',
        'user',
        'created_at',
    ]
    list_filter = ['status', 'course', 'created_at']
    search_fields = ['email', 'phone', 'token', 'kaspi_payment_id']
    readonly_fields = [
        'token',
        'kaspi_payment_id',
        'kaspi_qr_token',
        'kaspi_qr_payload',
        'created_at',
        'paid_at',
        'completed_at',
        'expires_at',
    ]
    raw_id_fields = ['user', 'course', 'group']

    fieldsets = (
        ('Основное', {
            'fields': ('email', 'phone', 'course', 'group', 'amount', 'status')
        }),
        ('Пользователь', {
            'fields': ('user',)
        }),
        ('Kaspi', {
            'fields': ('kaspi_payment_id', 'kaspi_qr_token', 'kaspi_qr_payload'),
            'classes': ('collapse',)
        }),
        ('Даты', {
            'fields': ('token', 'created_at', 'expires_at', 'paid_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )

    def formatted_amount(self, obj):
        return f"{obj.amount:,.0f} ₸"
    formatted_amount.short_description = 'Сумма'

    def status_badge(self, obj):
        colors = {
            'pending': '#FFA500',  # Orange
            'paid': '#4CAF50',     # Green
            'expired': '#9E9E9E',  # Gray
            'completed': '#2196F3', # Blue
            'cancelled': '#F44336', # Red
        }
        color = colors.get(obj.status, '#000')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Статус'

    actions = ['mark_as_expired', 'resend_payment_email']

    def mark_as_expired(self, request, queryset):
        count = queryset.filter(status='pending').update(status='expired')
        self.message_user(request, f'Помечено как истёкшие: {count}')
    mark_as_expired.short_description = 'Пометить как истёкшие'

    def resend_payment_email(self, request, queryset):
        from .services import PaymentEmailService
        count = 0
        for order in queryset.filter(status='paid', user__isnull=True):
            PaymentEmailService.send_complete_registration_reminder(order)
            count += 1
        self.message_user(request, f'Отправлено напоминаний: {count}')
    resend_payment_email.short_description = 'Отправить напоминание о регистрации'
