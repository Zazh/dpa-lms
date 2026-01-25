from django.contrib import admin
from django.utils.html import format_html
from .models import Certificate, CertificateTemplate


@admin.register(CertificateTemplate)
class CertificateTemplateAdmin(admin.ModelAdmin):
    list_display = ['course', 'signer_name', 'stamp_css_class', 'updated_at']
    search_fields = ['course__title', 'full_course_title', 'signer_name']

    fieldsets = (
        ('Курс', {
            'fields': ('course', 'full_course_title')
        }),
        ('Дата выдачи', {
            'fields': ('issue_date_label',),
            'description': 'Оставьте пустым, если дата не нужна на сертификате'
        }),
        ('Печать и подпись', {
            'fields': ('stamp_css_class', 'signature_css_class')
        }),
        ('Подписант', {
            'fields': ('signer_name', 'signer_position')
        }),
        ('Тексты сертификата', {
            'fields': ('certificate_title', 'completion_text'),
            'classes': ('collapse',)
        }),
        ('Тексты справки "Прослушал"', {
            'fields': ('attended_title', 'attended_text'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = [
        'number',
        'holder_name',
        'course_title',
        'type_badge',
        'source_badge',
        'status_badge',
        'issued_at',
    ]

    list_filter = ['certificate_type', 'source', 'status', 'issued_at']
    search_fields = ['number', 'holder_name', 'course_title']
    readonly_fields = ['created_at', 'updated_at']

    def type_badge(self, obj):
        colors = {
            'certificate': '#22c55e',
            'attended': '#f59e0b',
        }
        color = colors.get(obj.certificate_type, '#6b7280')
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; '
            'border-radius: 4px; font-size: 11px;">{}</span>',
            color,
            obj.get_certificate_type_display()
        )

    type_badge.short_description = 'Тип'

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