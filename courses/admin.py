from django.contrib import admin
from django.utils.html import format_html
from .models import Course, Lesson, CourseEnrollment, LessonProgress, LessonMaterial


class LessonMaterialInline(admin.TabularInline):
    """Inline для материалов урока"""
    model = LessonMaterial
    extra = 1
    fields = ('title', 'description', 'file', 'url', 'order')


class LessonInline(admin.TabularInline):
    """Inline для уроков в курсе"""
    model = Lesson
    extra = 1
    fields = ('order', 'title', 'video_url', 'requires_previous_completion', 'is_active')
    ordering = ['order']


class CourseEnrollmentInline(admin.TabularInline):
    """Inline для записей студентов на курс"""
    model = CourseEnrollment
    extra = 0
    readonly_fields = ('enrolled_at', 'get_progress')
    fields = ('user', 'enrolled_at', 'get_progress')

    def get_progress(self, obj):
        """Отображение прогресса студента"""
        if obj.pk:
            progress = obj.get_progress_percentage()
            color = 'green' if progress == 100 else 'orange' if progress > 50 else 'red'
            return format_html(
                '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
                color, progress
            )
        return '-'

    get_progress.short_description = 'Прогресс'


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'get_lessons_count', 'get_students_count', 'is_active', )
    list_filter = ('is_active', 'created_at', 'label')
    search_fields = ('title', 'description', 'label')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [LessonInline, CourseEnrollmentInline]

    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'label', 'duration', 'description', 'created_by', 'is_active')
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_lessons_count(self, obj):
        """Количество уроков"""
        count = obj.get_total_lessons()
        return format_html('<b>{}</b>', count)

    get_lessons_count.short_description = 'Уроков'

    def get_students_count(self, obj):
        """Количество студентов"""
        count = obj.get_enrolled_students_count()
        return format_html('<b>{}</b>', count)

    get_students_count.short_description = 'Студентов'

    def save_model(self, request, obj, form, change):
        """Автоматически устанавливать создателя курса"""
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = (
    'get_lesson_title', 'course', 'order', 'has_video', 'get_materials_count', 'requires_previous_completion',
    'is_active')
    list_filter = ('course', 'requires_previous_completion', 'is_active', 'created_at')
    search_fields = ('title', 'description', 'course__title')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [LessonMaterialInline]

    fieldsets = (
        ('Основная информация', {
            'fields': ('course', 'title', 'description', 'content')
        }),
        ('Видео', {
            'fields': ('video_url', 'video_duration', 'timecodes'),
            'description': 'Таймкоды в формате JSON: [{"time": "00:30", "title": "Введение"}, {"time": "05:15", "title": "Основная часть"}]'
        }),
        ('Настройки', {
            'fields': ('order', 'requires_previous_completion', 'is_active')
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_lesson_title(self, obj):
        """Отображение урока с номером"""
        return f"{obj.order}. {obj.title}"

    get_lesson_title.short_description = 'Урок'

    def has_video(self, obj):
        """Есть ли видео"""
        if obj.video_url:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')

    has_video.short_description = 'Видео'

    def get_materials_count(self, obj):
        """Количество материалов"""
        count = obj.materials.count()
        return format_html('<b>{}</b>', count) if count > 0 else '-'

    get_materials_count.short_description = 'Материалов'


@admin.register(LessonMaterial)
class LessonMaterialAdmin(admin.ModelAdmin):
    list_display = ('title', 'lesson', 'get_type', 'file_size_display', 'order', 'created_at')
    list_filter = ('lesson__course', 'file_type', 'created_at')
    search_fields = ('title', 'description', 'lesson__title')
    readonly_fields = ('file_size', 'file_type', 'created_at')

    fieldsets = (
        ('Основная информация', {
            'fields': ('lesson', 'title', 'description', 'order')
        }),
        ('Файл или ссылка', {
            'fields': ('file', 'url', 'file_size', 'file_type'),
            'description': 'Загрузите файл ИЛИ укажите ссылку (не оба одновременно)'
        }),
        ('Даты', {
            'fields': ('created_at',)
        }),
    )

    def get_type(self, obj):
        """Тип материала"""
        if obj.file:
            return format_html('<span style="color: blue;">📄 Файл ({})</span>', obj.file_type.upper())
        elif obj.url:
            return format_html('<span style="color: green;">🔗 Ссылка</span>')
        return '-'

    get_type.short_description = 'Тип'

    def file_size_display(self, obj):
        """Размер файла в читаемом формате"""
        if obj.file_size:
            if obj.file_size < 1024:
                return f"{obj.file_size} Б"
            elif obj.file_size < 1024 * 1024:
                return f"{obj.file_size / 1024:.1f} КБ"
            else:
                return f"{obj.file_size / (1024 * 1024):.1f} МБ"
        return '-'

    file_size_display.short_description = 'Размер'


@admin.register(CourseEnrollment)
class CourseEnrollmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'course', 'get_progress_display', 'enrolled_at')
    list_filter = ('course', 'enrolled_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'course__title')
    readonly_fields = ('enrolled_at', 'get_progress_display')

    fieldsets = (
        ('Информация', {
            'fields': ('user', 'course', 'enrolled_at', 'get_progress_display')
        }),
    )

    def get_progress_display(self, obj):
        """Отображение прогресса с цветом"""
        if obj.pk:
            progress = obj.get_progress_percentage()
            color = 'green' if progress == 100 else 'orange' if progress > 50 else 'red'
            return format_html(
                '<div style="background: {}; color: white; padding: 5px 10px; border-radius: 5px; text-align: center; width: 80px;">'
                '<b>{:.1f}%</b></div>',
                color, progress
            )
        return '-'

    get_progress_display.short_description = 'Прогресс'


@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_lesson_info', 'is_completed', 'started_at', 'completed_at')
    list_filter = ('is_completed', 'lesson__course', 'started_at', 'completed_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'lesson__title')
    readonly_fields = ('started_at', 'completed_at')

    fieldsets = (
        ('Информация', {
            'fields': ('user', 'lesson', 'is_completed')
        }),
        ('Даты', {
            'fields': ('started_at', 'completed_at')
        }),
    )

    def get_lesson_info(self, obj):
        """Информация об уроке"""
        return format_html(
            '<b>{}</b><br><small>{}</small>',
            obj.lesson.course.title,
            obj.lesson.title
        )

    get_lesson_info.short_description = 'Курс / Урок'