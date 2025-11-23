from django.contrib import admin
from django.utils.html import format_html
from .models import EmailLog, Notification, NotificationPreference


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'recipient', 'email_type_display', 'status_badge', 'created_at', 'sent_at']
    list_filter = ['status', 'email_type', 'created_at']
    search_fields = ['recipient', 'subject', 'user__email', 'user__first_name', 'user__last_name']
    readonly_fields = ['user', 'recipient', 'email_type', 'subject', 'status',
                       'error_message', 'sendpulse_response', 'created_at', 'sent_at']
    date_hierarchy = 'created_at'

    list_per_page = 50

    def email_type_display(self, obj):
        return obj.get_email_type_display()

    email_type_display.short_description = 'Тип письма'

    def status_badge(self, obj):
        colors = {
            'pending': '#ffc107',
            'sent': '#28a745',
            'failed': '#dc3545',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            colors.get(obj.status, '#6c757d'),
            obj.get_status_display()
        )

    status_badge.short_description = 'Статус'

    fieldsets = (
        ('Получатель', {
            'fields': ('user', 'recipient')
        }),
        ('Информация о письме', {
            'fields': ('email_type', 'subject', 'status')
        }),
        ('Детали отправки', {
            'fields': ('created_at', 'sent_at', 'error_message', 'sendpulse_response')
        }),
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'type', 'created_at']
    list_filter = ['type', 'created_at']
    search_fields = ['title', 'message', 'user__email', 'user__first_name', 'user__last_name']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Основное', {
            'fields': ('user', 'type')
        }),
        ('Содержание', {
            'fields': ('title', 'message', 'link')
        }),
        ('Дополнительно', {
            'fields': ('created_at',)
        }),
    )

    def get_queryset(self, request):
        """Оптимизация запросов"""
        qs = super().get_queryset(request)
        return qs.select_related('user')


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ['user', 'updated_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Пользователь', {
            'fields': ('user',)
        }),
        ('Урок доступен', {
            'fields': (
                'lesson_available_email',
                'lesson_available_push',
                'lesson_available_in_app',
            ),
        }),
        ('Домашнее задание принято', {
            'fields': (
                'homework_accepted_email',
                'homework_accepted_push',
                'homework_accepted_in_app',
            ),
        }),
        ('Домашнее задание требует доработки', {
            'fields': (
                'homework_needs_revision_email',
                'homework_needs_revision_push',
                'homework_needs_revision_in_app',
            ),
        }),
        ('Курс завершен', {
            'fields': (
                'course_completed_email',
                'course_completed_push',
                'course_completed_in_app',
            ),
        }),
        ('Акции и промо', {
            'fields': (
                'promotion_email',
                'promotion_push',
                'promotion_in_app',
            ),
        }),
        ('Массовые рассылки', {
            'fields': (
                'bulk_notifications_email',
                'bulk_notifications_push',
                'bulk_notifications_in_app',
            ),
        }),
        ('Поддержка', {
            'fields': (
                'support_reply_email',
                'support_reply_push',
                'support_reply_in_app',
            ),
        }),
        ('Системные', {
            'fields': (
                'system_email',
                'system_in_app',
            ),
        }),
        ('Временные метки', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        """Оптимизация запросов"""
        qs = super().get_queryset(request)
        return qs.select_related('user')