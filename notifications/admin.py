from django.contrib import admin
from django.utils.html import format_html
from .models import EmailLog


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