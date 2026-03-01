from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count
from .models import Course, Module, Lesson, VideoLesson, TextLesson, LessonMaterial


class ModuleInline(admin.TabularInline):
    """Inline для модулей курса"""
    model = Module
    extra = 0
    fields = ['order', 'title', 'lessons_count']
    readonly_fields = ['lessons_count']
    ordering = ['order']

    def lessons_count(self, obj):
        if obj.pk:
            return obj.get_lessons_count()
        return 0

    lessons_count.short_description = '📚 Уроков'


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['title', 'label', 'duration', 'status_badge', 'modules_count', 'lessons_count', 'students_count',
                    'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['title', 'label', 'description']
    readonly_fields = ['created_by', 'created_at', 'updated_at', 'modules_count', 'lessons_count', 'students_count']

    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'label', 'duration', 'description', 'project_url')
        }),
        ('Статус', {
            'fields': ('is_active',)
        }),
        ('Статистика', {
            'fields': ('modules_count', 'lessons_count', 'students_count'),
            'classes': ('collapse',)
        }),
        ('Системная информация', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    inlines = [ModuleInline]

    def save_model(self, request, obj, form, change):
        if not change:  # Создание нового курса
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def status_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 10px; border-radius: 3px;">✅ Активен</span>'
            )
        return format_html(
            '<span style="background-color: #dc3545; color: white; padding: 3px 10px; border-radius: 3px;">❌ Неактивен</span>'
        )

    status_badge.short_description = 'Статус'

    def modules_count(self, obj):
        return obj.get_modules_count()

    modules_count.short_description = '📦 Модулей'

    def lessons_count(self, obj):
        return obj.get_lessons_count()

    lessons_count.short_description = '📚 Уроков'

    def students_count(self, obj):
        return obj.get_enrolled_students_count()

    students_count.short_description = '👥 Студентов'

    actions = ['activate_courses', 'deactivate_courses']

    def activate_courses(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'✅ Активировано курсов: {updated}')

    activate_courses.short_description = '✅ Активировать выбранные курсы'

    def deactivate_courses(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'❌ Деактивировано курсов: {updated}')

    deactivate_courses.short_description = '❌ Деактивировать выбранные курсы'


class LessonInline(admin.TabularInline):
    """Inline для уроков модуля"""
    model = Lesson
    extra = 0
    fields = ['order', 'lesson_type', 'title', 'access_delay_hours', 'requires_previous_completion']
    ordering = ['order']


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ['title', 'course', 'order', 'lessons_count', 'created_at']
    list_filter = ['course', 'created_at']
    search_fields = ['title', 'description', 'course__title']
    readonly_fields = ['created_at', 'updated_at', 'lessons_count']

    fieldsets = (
        ('Основная информация', {
            'fields': ('course', 'title', 'description', 'order')
        }),
        ('Статистика', {
            'fields': ('lessons_count',),
            'classes': ('collapse',)
        }),
        ('Системная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    inlines = [LessonInline]

    def lessons_count(self, obj):
        if obj.pk:
            return obj.get_lessons_count()
        return 0

    lessons_count.short_description = '📚 Уроков'


class VideoLessonInline(admin.StackedInline):
    """Inline для видео-урока"""
    model = VideoLesson
    extra = 0
    fields = ['vimeo_video_id', 'video_duration', 'completion_threshold', 'timecodes', 'thumbnail']
    readonly_fields = ['video_duration']

    def has_add_permission(self, request, obj=None):
        # Можно добавить только если тип урока - video
        if obj and obj.lesson_type == 'video':
            return True
        return False


class TextLessonInline(admin.StackedInline):
    """Inline для текстового урока"""
    model = TextLesson
    extra = 0
    fields = ['content', 'estimated_reading_time']

    def has_add_permission(self, request, obj=None):
        # Можно добавить только если тип урока - text
        if obj and obj.lesson_type == 'text':
            return True
        return False


class LessonMaterialInline(admin.TabularInline):
    """Inline для материалов урока"""
    model = LessonMaterial
    extra = 0
    fields = ['order', 'title', 'file', 'url']
    ordering = ['order']


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ['title', 'type_badge', 'module', 'order', 'access_delay_badge', 'requires_completion_badge',
                    'materials_count']
    list_filter = ['lesson_type', 'module__course', 'requires_previous_completion']
    search_fields = ['title', 'description', 'module__title']
    readonly_fields = ['created_at', 'updated_at', 'materials_count', 'type_instance_info']

    fieldsets = (
        ('Основная информация', {
            'fields': ('module', 'lesson_type', 'title', 'description', 'order')
        }),
        ('Настройки доступа', {
            'fields': ('access_delay_hours', 'requires_previous_completion')
        }),
        ('Статистика', {
            'fields': ('materials_count', 'type_instance_info'),
            'classes': ('collapse',)
        }),
        ('Системная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    inlines = [VideoLessonInline, TextLessonInline, LessonMaterialInline]

    def get_inline_instances(self, request, obj=None):
        """Показываем только нужный inline в зависимости от типа урока"""
        if obj:
            if obj.lesson_type == 'video':
                return [inline(self.model, self.admin_site) for inline in [VideoLessonInline, LessonMaterialInline]]
            elif obj.lesson_type == 'text':
                return [inline(self.model, self.admin_site) for inline in [TextLessonInline, LessonMaterialInline]]
            elif obj.lesson_type in ['quiz', 'assignment']:
                # Для quiz и assignment покажем только материалы, сами quiz/assignment будут в других приложениях
                return [inline(self.model, self.admin_site) for inline in [LessonMaterialInline]]
        return []

    def type_badge(self, obj):
        colors = {
            'video': '#007bff',
            'text': '#28a745',
            'quiz': '#ffc107',
            'assignment': '#dc3545',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            colors.get(obj.lesson_type, '#6c757d'),
            obj.get_lesson_type_display()
        )

    type_badge.short_description = 'Тип'

    def access_delay_badge(self, obj):
        if obj.access_delay_hours > 0:
            return f'⏰ {obj.access_delay_hours}ч'
        return '🔓 Сразу'

    access_delay_badge.short_description = 'Задержка'

    def requires_completion_badge(self, obj):
        return '✅ Да' if obj.requires_previous_completion else '❌ Нет'

    requires_completion_badge.short_description = 'Требует завершения'

    def materials_count(self, obj):
        if obj.pk:
            return obj.get_materials_count()
        return 0

    materials_count.short_description = '📎 Материалов'

    def type_instance_info(self, obj):
        """Информация о конкретном типе урока"""
        if not obj.pk:
            return '-'

        instance = obj.get_type_instance()
        if not instance:
            return format_html('<span style="color: #dc3545;">⚠️ Данные для типа урока не созданы</span>')

        if obj.lesson_type == 'video':
            return format_html(
                '📹 Видео ID: {} | Длительность: {} | Порог: {}%',
                instance.vimeo_video_id,
                instance.format_duration(),
                instance.completion_threshold
            )
        elif obj.lesson_type == 'text':
            return format_html(
                '📄 Слов: {} | Время чтения: {} мин',
                instance.get_word_count(),
                instance.estimated_reading_time
            )

        return '-'

    type_instance_info.short_description = 'Детали урока'


@admin.register(VideoLesson)
class VideoLessonAdmin(admin.ModelAdmin):
    list_display = ['lesson', 'vimeo_video_id', 'formatted_duration', 'completion_threshold']
    search_fields = ['lesson__title', 'vimeo_video_id']
    readonly_fields = ['video_duration', 'formatted_duration', 'embed_url', 'thumbnail_preview']

    fieldsets = (
        ('Связь с уроком', {
            'fields': ('lesson',)
        }),
        ('Настройки видео', {
            'fields': ('vimeo_video_id', 'video_duration', 'formatted_duration', 'embed_url', 'completion_threshold')
        }),
        ('Обложка', {  # ← ДОБАВИТЬ
            'fields': ('thumbnail', 'thumbnail_preview')
        }),
        ('Дополнительно', {
            'fields': ('timecodes',),
            'classes': ('collapse',)
        }),
    )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Показывать только уроки с типом 'video'"""
        if db_field.name == "lesson":
            kwargs["queryset"] = Lesson.objects.filter(lesson_type='video')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formatted_duration(self, obj):
        if obj.pk:
            return obj.format_duration()
        return '-'

    formatted_duration.short_description = 'Длительность'

    def embed_url(self, obj):
        if obj.pk:
            url = obj.get_vimeo_embed_url()
            return format_html('<a href="{}" target="_blank">{}</a>', url, url)
        return '-'

    embed_url.short_description = 'Embed URL'

    def has_thumbnail(self, obj):
        return '✅ Да' if obj.thumbnail else '❌ Нет'

    has_thumbnail.short_description = 'Обложка'

    def thumbnail_preview(self, obj):
        if obj.thumbnail:
            return format_html(
                '<img src="{}" style="max-width: 400px; max-height: 225px; border-radius: 8px;" />',
                obj.thumbnail.url
            )
        return 'Нет обложки'

    thumbnail_preview.short_description = 'Превью обложки'


@admin.register(TextLesson)
class TextLessonAdmin(admin.ModelAdmin):
    list_display = ['lesson', 'word_count', 'estimated_reading_time']
    search_fields = ['lesson__title', 'content']
    readonly_fields = ['word_count']

    fieldsets = (
        ('Связь с уроком', {
            'fields': ('lesson',)
        }),
        ('Содержимое', {
            'fields': ('content', 'estimated_reading_time', 'word_count')
        }),
    )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Показывать только уроки с типом 'text'"""
        if db_field.name == "lesson":
            kwargs["queryset"] = Lesson.objects.filter(lesson_type='text')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def word_count(self, obj):
        if obj.pk:
            return f'📝 {obj.get_word_count()} слов'
        return '-'

    word_count.short_description = 'Количество слов'

@admin.register(LessonMaterial)
class LessonMaterialAdmin(admin.ModelAdmin):
    list_display = ['title', 'lesson', 'order', 'has_file', 'has_url']
    list_filter = ['lesson__module__course']
    search_fields = ['title', 'description', 'lesson__title']
    readonly_fields = ['created_at', 'file_size_display']

    fieldsets = (
        ('Основная информация', {
            'fields': ('lesson', 'title', 'description', 'order')
        }),
        ('Контент', {
            'fields': ('file', 'file_size_display', 'url')
        }),
        ('Системная информация', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def has_file(self, obj):
        return '📎 Да' if obj.file else '❌ Нет'

    has_file.short_description = 'Файл'

    def has_url(self, obj):
        return '🔗 Да' if obj.url else '❌ Нет'

    has_url.short_description = 'Ссылка'

    def file_size_display(self, obj):
        if obj.pk and obj.file:
            size = obj.get_file_size()
            return f'📦 {size}' if size else '-'
        return '-'

    file_size_display.short_description = 'Размер файла'