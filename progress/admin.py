from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Avg
from .models import CourseEnrollment, LessonProgress, VideoProgress


@admin.register(CourseEnrollment)
class CourseEnrollmentAdmin(admin.ModelAdmin):
    list_display = ['user_info', 'course', 'group', 'access_badge', 'progress_bar', 'completed_lessons_info',
                    'enrolled_at', 'last_activity_at']
    list_filter = ['is_active', 'course', 'group', 'enrolled_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'course__title']
    readonly_fields = ['enrolled_at', 'progress_percentage', 'completed_lessons_count', 'last_activity_at',
                       'current_lesson_display', 'completed_modules_display', 'access_status_display']
    date_hierarchy = 'enrolled_at'

    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'course', 'group', 'is_active')
        }),
        ('Доступ', {
            'fields': ('access_status_display',)
        }),
        ('Прогресс', {
            'fields': ('progress_percentage', 'completed_lessons_count', 'current_lesson_display',
                       'completed_modules_display')
        }),
        ('Даты', {
            'fields': ('enrolled_at', 'last_activity_at')
        }),
    )

    actions = ['sync_access_status']

    def user_info(self, obj):
        return f"{obj.user.get_full_name()} ({obj.user.email})"

    user_info.short_description = 'Студент'

    def access_badge(self, obj):
        """Бейдж доступа на основе GroupMembership"""
        if obj.has_access():
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 10px; border-radius: 3px;">✅ Доступ есть</span>'
            )
        return format_html(
            '<span style="background-color: #dc3545; color: white; padding: 3px 10px; border-radius: 3px;">❌ Доступа нет</span>'
        )

    access_badge.short_description = 'Доступ'

    def access_status_display(self, obj):
        """Детальный статус доступа"""
        if not obj.group:
            return '❌ Не привязан к группе'

        from groups.models import GroupMembership
        membership = GroupMembership.objects.filter(
            user=obj.user,
            group=obj.group,
            is_active=True
        ).first()

        if not membership:
            return f'❌ Нет активного членства в группе "{obj.group.name}"'

        deadline_info = ''
        if membership.personal_deadline_at:
            days_left = membership.get_days_until_deadline()
            if days_left == 0:
                deadline_info = ' (дедлайн истёк)'
            elif days_left and days_left <= 7:
                deadline_info = f' (осталось {days_left} дн.)'

        return f'✅ Активное членство в группе "{obj.group.name}"{deadline_info}'

    access_status_display.short_description = 'Статус доступа'

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

    def sync_access_status(self, request, queryset):
        """Синхронизировать статус доступа с GroupMembership"""
        count = 0
        for enrollment in queryset:
            enrollment.sync_active_status()
            count += 1
        self.message_user(request, f'🔄 Синхронизировано: {count}')

    sync_access_status.short_description = '🔄 Синхронизировать доступ'

@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = ['user_info', 'lesson_info', 'completion_badge', 'started_at', 'completed_at', 'completed_ip',
                    'duration_display', 'available_badge']
    list_filter = ['is_completed', 'lesson__lesson_type', 'lesson__module__course', 'completed_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'lesson__title']
    readonly_fields = ['started_at', 'completed_at', 'available_at', 'duration_display', 'completion_data_display',
                       'completed_ip', 'completed_user_agent']
    date_hierarchy = 'completed_at'

    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'lesson', 'is_completed')
        }),
        ('Даты', {
            'fields': ('started_at', 'completed_at', 'available_at', 'duration_display')
        }),
        ('IP / Браузер при завершении', {
            'fields': ('completed_ip', 'completed_user_agent')
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
    mark_completed.short_description = '🔧 [Служебное] Вручную завершить урок'

    def mark_uncompleted(self, request, queryset):
        updated = queryset.update(is_completed=False, completed_at=None)

        # ВАЖНО: Пересчитать прогресс курса после отмены
        for progress in queryset:
            try:
                from content.models import Lesson
                enrollment = CourseEnrollment.objects.get(
                    user=progress.user,
                    course=progress.lesson.module.course
                )
                enrollment.calculate_progress()
            except CourseEnrollment.DoesNotExist:
                pass

        self.message_user(request, f'⏳ Отмечено незавершенными: {updated}')

    mark_uncompleted.short_description = '🔧 [Служебное] Отменить завершение'

    def recalculate_availability(self, request, queryset):
        count = 0
        for progress in queryset:
            progress.calculate_available_at()
            count += 1
        self.message_user(request, f'🔄 Пересчитана доступность для {count} записей')
    recalculate_availability.short_description = '🔧 [Служебное] Пересчитать доступность'


@admin.register(VideoProgress)
class VideoProgressAdmin(admin.ModelAdmin):
    list_display = ['user_info', 'video_lesson_title', 'watch_percentage_display', 'is_completed_badge', 'started_at',
                    'last_watched_at']
    list_filter = ['started_at', 'last_watched_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'video_lesson__lesson__title']
    readonly_fields = ['started_at', 'last_watched_at']

    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'video_lesson', 'watch_percentage')
        }),
        ('Даты', {
            'fields': ('started_at', 'last_watched_at')
        }),
    )

    def user_info(self, obj):
        return f"{obj.user.get_full_name()} ({obj.user.email})"

    user_info.short_description = 'Пользователь'

    def video_lesson_title(self, obj):
        return obj.video_lesson.lesson.title

    video_lesson_title.short_description = 'Видео-урок'

    def watch_percentage_display(self, obj):
        percentage = float(obj.watch_percentage)
        color = '#28a745' if percentage >= 90 else '#ffc107' if percentage >= 50 else '#dc3545'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}%</span>',
            color, int(percentage)
        )

    watch_percentage_display.short_description = 'Просмотр'

    def is_completed_badge(self, obj):
        if obj.is_mostly_watched():
            return '✅ Завершено'
        return '⏳ В процессе'

    is_completed_badge.short_description = 'Статус'