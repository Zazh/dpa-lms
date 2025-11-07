from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Avg
from .models import Graduate, GraduateAchievement


class GraduateAchievementInline(admin.TabularInline):
    """Inline для достижений"""
    model = GraduateAchievement
    extra = 0
    fields = ['achievement_type', 'description', 'earned_at']
    readonly_fields = ['earned_at']


@admin.register(Graduate)
class GraduateAdmin(admin.ModelAdmin):
    list_display = ['user_info', 'course', 'group', 'final_score_badge', 'certificate_status_badge', 'graduated_at',
                    'study_duration']
    list_filter = ['course', 'group', 'graduated_at', 'certificate_issued_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'course__title', 'certificate_number']
    readonly_fields = ['graduated_at', 'total_lessons_completed', 'average_quiz_score', 'total_study_days',
                       'certificate_number']
    date_hierarchy = 'graduated_at'

    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'course', 'group', 'graduated_at')
        }),
        ('Результаты обучения', {
            'fields': ('final_score', 'total_lessons_completed', 'average_quiz_score', 'total_study_days')
        }),
        ('Сертификат', {
            'fields': ('certificate_number', 'certificate_file', 'certificate_issued_at')
        }),
        ('Дополнительно', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )

    inlines = [GraduateAchievementInline]
    actions = ['issue_certificates', 'regenerate_certificate_numbers']

    def user_info(self, obj):
        return f"🎓 {obj.user.get_full_name()} ({obj.user.email})"

    user_info.short_description = 'Выпускник'

    def final_score_badge(self, obj):
        score = float(obj.final_score)
        if score >= 90:
            color = '#28a745'
            icon = '🏆'
        elif score >= 80:
            color = '#17a2b8'
            icon = '⭐'
        elif score >= 70:
            color = '#ffc107'
            icon = '✅'
        else:
            color = '#6c757d'
            icon = '📝'

        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{} {}%</span>',
            color, icon, int(score)
        )

    final_score_badge.short_description = 'Итоговая оценка'

    def certificate_status_badge(self, obj):
        if obj.certificate_issued_at:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 10px; border-radius: 3px;">📜 Выдан</span><br>'
                '<small style="color: #6c757d;">{}</small>',
                obj.certificate_number
            )
        return format_html(
            '<span style="background-color: #ffc107; color: white; padding: 3px 10px; border-radius: 3px;">⏳ Ожидает</span>')

    certificate_status_badge.short_description = 'Сертификат'

    def study_duration(self, obj):
        return f'📅 {obj.total_study_days} дн.'

    study_duration.short_description = 'Длительность'

    def issue_certificates(self, request, queryset):
        """Выдать сертификаты"""
        count = 0
        for graduate in queryset.filter(certificate_issued_at__isnull=True):
            graduate.issue_certificate()
            count += 1

        self.message_user(request, f'📜 Выдано сертификатов: {count}')

    issue_certificates.short_description = '📜 Выдать сертификаты'

    def regenerate_certificate_numbers(self, request, queryset):
        """Перегенерировать номера сертификатов"""
        count = 0
        for graduate in queryset:
            graduate.certificate_number = None
            graduate.generate_certificate_number()
            count += 1

        self.message_user(request, f'🔄 Обновлено номеров: {count}')

    regenerate_certificate_numbers.short_description = '🔄 Перегенерировать номера'


@admin.register(GraduateAchievement)
class GraduateAchievementAdmin(admin.ModelAdmin):
    list_display = ['graduate_info', 'achievement_badge', 'earned_at']
    list_filter = ['achievement_type', 'earned_at']
    search_fields = ['graduate__user__email', 'graduate__user__first_name', 'graduate__user__last_name']
    readonly_fields = ['earned_at']

    def graduate_info(self, obj):
        return f"{obj.graduate.user.get_full_name()} - {obj.graduate.course.title}"

    graduate_info.short_description = 'Выпускник'

    def achievement_badge(self, obj):
        return format_html(
            '<span style="font-size: 16px;">{}</span>',
            obj.get_achievement_type_display()
        )

    achievement_badge.short_description = 'Достижение'