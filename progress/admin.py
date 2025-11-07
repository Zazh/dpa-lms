from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Avg
from .models import CourseEnrollment, LessonProgress, VideoProgress


@admin.register(CourseEnrollment)
class CourseEnrollmentAdmin(admin.ModelAdmin):
    list_display = ['user_info', 'course', 'group', 'payment_badge', 'progress_bar', 'completed_lessons_info',
                    'enrolled_at', 'last_activity_at', 'status_badge']
    list_filter = ['is_active', 'payment_status', 'course', 'group', 'enrolled_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'course__title']
    readonly_fields = ['enrolled_at', 'progress_percentage', 'completed_lessons_count', 'last_activity_at',
                       'current_lesson_display', 'completed_modules_display']
    date_hierarchy = 'enrolled_at'

    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'course', 'group', 'payment_status', 'is_active')
        }),
        ('Прогресс', {
            'fields': ('progress_percentage', 'completed_lessons_count', 'current_lesson_display',
                       'completed_modules_display')
        }),
        ('Даты', {
            'fields': ('enrolled_at', 'last_activity_at')
        }),
    )

    actions = ['recalculate_progress', 'activate_enrollments', 'deactivate_enrollments', 'mark_as_paid']

    def user_info(self, obj):
        return f"{obj.user.get_full_name()} ({obj.user.email})"

    user_info.short_description = 'Студент'

    def payment_badge(self, obj):
        colors = {
            'unpaid': '#dc3545',
            'paid': '#28a745',
            'trial': '#17a2b8',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            colors.get(obj.payment_status, '#6c757d'),
            obj.get_payment_status_display()
        )

    payment_badge.short_description = 'Оплата'

    def progress_bar(self, obj):
        percentage = float(obj.progress_percentage)
        color = '#28a745' if percentage >= 80 else '#ffc107' if percentage >= 50 else '#dc3545'
        return format_html(
            '<div style="width: 100px; background-color: #e9ecef; border-radius: 4px; overflow: hidden;">'
            '<div style="width: {}%; background-color: {}; color: white; text-align: center; padding: 2px 0; font-size: 11px;">'
            '{}%'
            '</div>'
            '</div>',
            percentage, color, int(percentage)
        )

    progress_bar.short_description = 'Прогресс'

    def completed_lessons_info(self, obj):
        from content.models import Lesson
        total = Lesson.objects.filter(module__course=obj.course).count()
        return f'📚 {obj.completed_lessons_count}/{total}'

    completed_lessons_info.short_description = 'Уроки'

    def status_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 10px; border-radius: 3px;">✅ Активно</span>')
        return format_html(
            '<span style="background-color: #6c757d; color: white; padding: 3px 10px; border-radius: 3px;">❌ Неактивно</span>')

    status_badge.short_description = 'Статус'

    def current_lesson_display(self, obj):
        lesson = obj.get_current_lesson()
        if lesson:
            return f'📖 {lesson.title}'
        return '✅ Все уроки завершены'

    current_lesson_display.short_description = 'Текущий урок'

    def completed_modules_display(self, obj):
        from content.models import Module
        total = Module.objects.filter(course=obj.course).count()
        completed = obj.get_completed_modules_count()
        return f'📦 {completed}/{total} модулей'

    completed_modules_display.short_description = 'Модули'

    def recalculate_progress(self, request, queryset):
        count = 0
        for enrollment in queryset:
            enrollment.calculate_progress()
            count += 1
        self.message_user(request, f'🔄 Пересчитан прогресс для {count} зачислений')

    recalculate_progress.short_description = '🔄 Пересчитать прогресс'

    def activate_enrollments(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'✅ Активировано: {updated}')

    activate_enrollments.short_description = '✅ Активировать зачисления'

    def deactivate_enrollments(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'❌ Деактивировано: {updated}')

    deactivate_enrollments.short_description = '❌ Деактивировать зачисления'

    def mark_as_paid(self, request, queryset):
        updated = queryset.update(payment_status='paid')
        self.message_user(request, f'💰 Отмечено как оплачено: {updated}')

    mark_as_paid.short_description = '💰 Отметить как оплачено'

@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = ['user_info', 'lesson_info', 'completion_badge', 'started_at', 'completed_at', 'duration_display',
                    'available_badge']
    list_filter = ['is_completed', 'lesson__lesson_type', 'lesson__module__course', 'completed_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'lesson__title']
    readonly_fields = ['started_at', 'completed_at', 'available_at', 'duration_display', 'completion_data_display']
    date_hierarchy = 'completed_at'

    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'lesson', 'is_completed')
        }),
        ('Даты', {
            'fields': ('started_at', 'completed_at', 'available_at', 'duration_display')
        }),
        ('Дополнительно', {
            'fields': ('completion_data', 'completion_data_display'),
            'classes': ('collapse',)
        }),
    )

    actions = ['mark_completed', 'mark_uncompleted', 'recalculate_availability']

    def user_info(self, obj):
        return f"{obj.user.get_full_name()}"

    user_info.short_description = 'Студент'

    def lesson_info(self, obj):
        return f"{obj.lesson.get_lesson_type_display()} - {obj.lesson.title}"

    lesson_info.short_description = 'Урок'

    def completion_badge(self, obj):
        if obj.is_completed:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 10px; border-radius: 3px;">✅ Завершен</span>')
        return format_html(
            '<span style="background-color: #ffc107; color: white; padding: 3px 10px; border-radius: 3px;">⏳ В процессе</span>')

    completion_badge.short_description = 'Статус'

    def available_badge(self, obj):
        if obj.is_available():
            return '🔓 Доступен'
        return '🔒 Недоступен'

    available_badge.short_description = 'Доступность'

    def duration_display(self, obj):
        seconds = obj.get_duration_seconds()
        if seconds > 0:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f'⏱️ {minutes}:{secs:02d}'
        return '-'

    duration_display.short_description = 'Длительность'

    def completion_data_display(self, obj):
        if obj.completion_data:
            items = []
            for key, value in obj.completion_data.items():
                items.append(f'{key}: {value}')
            return format_html('<br>'.join(items))
        return 'Нет данных'

    completion_data_display.short_description = 'Данные о завершении'

    def mark_completed(self, request, queryset):
        count = 0
        for progress in queryset.filter(is_completed=False):
            progress.mark_completed()
            count += 1
        self.message_user(request, f'✅ Отмечено завершенными: {count}')

    mark_completed.short_description = '✅ Отметить завершенными'

    def mark_uncompleted(self, request, queryset):
        updated = queryset.update(is_completed=False, completed_at=None)
        self.message_user(request, f'⏳ Отмечено незавершенными: {updated}')

    mark_uncompleted.short_description = '⏳ Отметить незавершенными'

    def recalculate_availability(self, request, queryset):
        count = 0
        for progress in queryset:
            progress.calculate_available_at()
            count += 1
        self.message_user(request, f'🔄 Пересчитана доступность для {count} записей')

    recalculate_availability.short_description = '🔄 Пересчитать доступность'


@admin.register(VideoProgress)
class VideoProgressAdmin(admin.ModelAdmin):
    list_display = ['user_info', 'video_lesson_info', 'progress_bar', 'watch_count', 'total_watch_time_display',
                    'completion_badge', 'last_watched_at']
    list_filter = ['is_completed', 'video_lesson__lesson__module__course', 'last_watched_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'video_lesson__lesson__title']
    readonly_fields = ['current_position', 'watch_percentage', 'total_watch_time', 'watch_count', 'last_watched_at',
                       'remaining_time_display', 'formatted_watch_time']
    date_hierarchy = 'last_watched_at'

    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'video_lesson', 'is_completed')
        }),
        ('Прогресс просмотра', {
            'fields': ('current_position', 'watch_percentage', 'remaining_time_display')
        }),
        ('Статистика', {
            'fields': ('watch_count', 'total_watch_time', 'formatted_watch_time', 'last_watched_at')
        }),
    )

    def user_info(self, obj):
        return f"{obj.user.get_full_name()}"

    user_info.short_description = 'Студент'

    def video_lesson_info(self, obj):
        return obj.video_lesson.lesson.title

    video_lesson_info.short_description = 'Видео'

    def progress_bar(self, obj):
        percentage = float(obj.watch_percentage)
        threshold = obj.video_lesson.completion_threshold
        color = '#28a745' if percentage >= threshold else '#ffc107' if percentage >= 50 else '#dc3545'
        return format_html(
            '<div style="width: 100px; background-color: #e9ecef; border-radius: 4px; overflow: hidden;">'
            '<div style="width: {}%; background-color: {}; color: white; text-align: center; padding: 2px 0; font-size: 11px;">'
            '{}%'
            '</div>'
            '</div>',
            min(percentage, 100), color, int(percentage)
        )

    progress_bar.short_description = 'Прогресс'

    def completion_badge(self, obj):
        if obj.is_completed:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 10px; border-radius: 3px;">✅ Завершен</span>')
        return format_html(
            '<span style="background-color: #ffc107; color: white; padding: 3px 10px; border-radius: 3px;">⏳ Просмотр</span>')

    completion_badge.short_description = 'Статус'

    def total_watch_time_display(self, obj):
        return obj.format_watch_time()

    total_watch_time_display.short_description = 'Время просмотра'

    def remaining_time_display(self, obj):
        remaining = obj.get_remaining_time()
        minutes = remaining // 60
        seconds = remaining % 60
        return f'{minutes}:{seconds:02d}'

    remaining_time_display.short_description = 'Осталось'

    def formatted_watch_time(self, obj):
        return obj.format_watch_time()

    formatted_watch_time.short_description = 'Общее время (ММ:СС)'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser