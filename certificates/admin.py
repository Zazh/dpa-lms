from django.contrib import admin
from django.utils.html import format_html
from .models import Certificate


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = [
        'number',
        'holder_name',
        'course_title',
        'source_badge',
        'status_badge',
        'issued_at',
        'created_at',
    ]

    list_filter = ['source', 'status', 'issued_at', 'created_at']
    search_fields = ['number', 'holder_name', 'course_title']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Основная информация', {
            'fields': ('number', 'holder_name', 'course_title', 'group_name')
        }),
        ('Источник и статус', {
            'fields': ('source', 'status', 'error_message')
        }),
        ('Связи', {
            'fields': ('user', 'graduate'),
            'classes': ('collapse',),
            'description': 'Для внутренних сертификатов заполняется автоматически'
        }),
        ('Файлы', {
            'fields': ('file_without_stamp', 'file_with_stamp')
        }),
        ('Даты', {
            'fields': ('issued_at', 'created_at', 'updated_at')
        }),
    )

    def source_badge(self, obj):
        colors = {
            'internal': '#22c55e',
            'external': '#3b82f6',
        }
        color = colors.get(obj.source, '#6b7280')
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; '
            'border-radius: 4px; font-size: 11px;">{}</span>',
            color,
            obj.get_source_display()
        )

    source_badge.short_description = 'Источник'

    def status_badge(self, obj):
        colors = {
            'pending': '#f59e0b',
            'ready': '#22c55e',
            'error': '#ef4444',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; '
            'border-radius: 4px; font-size: 11px;">{}</span>',
            color,
            obj.get_status_display()
        )

    status_badge.short_description = 'Статус'

    def get_readonly_fields(self, request, obj=None):
        """Для внутренних сертификатов — больше readonly полей"""
        readonly = list(self.readonly_fields)
        if obj and obj.source == 'internal':
            readonly.extend(['number', 'holder_name', 'course_title', 'group_name', 'user', 'graduate', 'issued_at'])
        return readonly

    def has_delete_permission(self, request, obj=None):
        """Удаление только для внешних или суперюзера"""
        if obj and obj.source == 'internal':
            return request.user.is_superuser
        return True