from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import (
    Course, Module, Lesson, CourseEnrollment, LessonProgress, LessonMaterial,
    VideoLesson, TextLesson, QuizLesson, AssignmentLesson,
    QuizQuestion, QuizAnswer, QuizAttempt, QuizResponse,
    AssignmentSubmission, AssignmentComment, VideoProgress
)


# ============================================================
# INLINE АДМИНКИ
# ============================================================

class LessonMaterialInline(admin.TabularInline):
    """Inline для материалов урока"""
    model = LessonMaterial
    extra = 1
    fields = ('title', 'description', 'file', 'url', 'order')


class LessonInline(admin.TabularInline):
    """Inline для уроков в модуле"""
    model = Lesson
    extra = 0
    fields = ('order', 'lesson_type', 'title', 'access_delay_hours', 'requires_previous_completion', 'is_active')
    ordering = ['order']
    readonly_fields = ('lesson_type',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('module')


class ModuleInline(admin.TabularInline):
    """Inline для модулей в курсе"""
    model = Module
    extra = 0
    fields = ('order', 'title', 'requires_previous_module', 'is_active')
    ordering = ['order']


class CourseEnrollmentInline(admin.TabularInline):
    """Inline для записей студентов на курс"""
    model = CourseEnrollment
    extra = 0
    readonly_fields = ('enrolled_at', 'get_progress', 'last_activity_at')
    fields = ('user', 'enrolled_at', 'get_progress', 'last_activity_at')

    def get_progress(self, obj):
        """Отображение прогресса студента"""
        if obj.pk:
            progress = obj.get_progress_percentage()
            # ← ИСПРАВЛЕНИЕ
            progress_value = float(progress) if progress else 0

            color = 'green' if progress_value == 100 else 'orange' if progress_value > 50 else 'red'

            # Форматируем число отдельно
            progress_str = f"{progress_value:.1f}"

            return format_html(
                '<span style="color: {}; font-weight: bold;">{}%</span>',
                color, progress_str  # ← Передаем строку
            )
        return '-'

    get_progress.short_description = 'Прогресс'


class QuizAnswerInline(admin.TabularInline):
    """Inline для вариантов ответов"""
    model = QuizAnswer
    extra = 4
    fields = ('order', 'answer_text', 'is_correct')
    ordering = ['order']


class QuizQuestionInline(admin.StackedInline):
    """Inline для вопросов теста"""
    model = QuizQuestion
    extra = 0
    fields = ('order', 'question_type', 'question_text', 'explanation', 'points', 'is_active')
    ordering = ['order']


class AssignmentCommentInline(admin.TabularInline):
    """Inline для комментариев к ДЗ"""
    model = AssignmentComment
    extra = 0
    readonly_fields = ('author', 'is_instructor', 'created_at')
    fields = ('author', 'message', 'is_instructor', 'created_at')
    ordering = ['created_at']

    def has_add_permission(self, request, obj=None):
        return False


# ============================================================
# ОСНОВНЫЕ АДМИНКИ
# ============================================================

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'label', 'duration', 'get_modules_count', 'get_students_count', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at', 'label')
    search_fields = ('title', 'description', 'label')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [ModuleInline, CourseEnrollmentInline]

    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'label', 'duration', 'description', 'created_by', 'is_active')
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_modules_count(self, obj):
        """Количество модулей"""
        count = obj.modules.count()
        return format_html('<b>{}</b>', count)

    get_modules_count.short_description = 'Модулей'

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


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ('get_module_title', 'course', 'order', 'get_lessons_count', 'requires_previous_module', 'is_active')
    list_filter = ('course', 'requires_previous_module', 'is_active')
    search_fields = ('title', 'description', 'course__title')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [LessonInline]

    fieldsets = (
        ('Основная информация', {
            'fields': ('course', 'title', 'description', 'order')
        }),
        ('Настройки', {
            'fields': ('requires_previous_module', 'is_active')
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_module_title(self, obj):
        """Отображение модуля с номером"""
        return f"Модуль {obj.order}: {obj.title}"

    get_module_title.short_description = 'Модуль'

    def get_lessons_count(self, obj):
        """Количество уроков"""
        count = obj.get_total_lessons()
        return format_html('<b>{}</b>', count)

    get_lessons_count.short_description = 'Уроков'


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = (
        'get_lesson_title',
        'module',  # ← ИСПРАВЛЕНО
        'get_lesson_type',
        'order',
        'access_delay_hours',
        'requires_previous_completion',
        'is_active'
    )
    list_filter = ('module__course', 'lesson_type', 'requires_previous_completion', 'is_active')  # ← ИСПРАВЛЕНО
    search_fields = ('title', 'description', 'module__title', 'module__course__title')  # ← ИСПРАВЛЕНО
    readonly_fields = ('created_at', 'updated_at')
    inlines = [LessonMaterialInline]

    fieldsets = (
        ('Основная информация', {
            'fields': ('module', 'lesson_type', 'title', 'description', 'order')
        }),
        ('Настройки доступа', {
            'fields': ('access_delay_hours', 'requires_previous_completion', 'is_active')
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

    def get_lesson_type(self, obj):
        """Отображение типа урока с иконкой"""
        icon = obj.get_lesson_type_display_icon()
        return format_html(
            '<span style="font-size: 16px;">{}</span> {}',
            icon,
            obj.get_lesson_type_display()
        )

    get_lesson_type.short_description = 'Тип'

    def save_model(self, request, obj, form, change):
        """Автоматически создать расширение при создании урока"""
        is_new = obj.pk is None
        super().save_model(request, obj, form, change)

        # Создаем расширение для нового урока
        if is_new:
            if obj.lesson_type == 'video' and not hasattr(obj, 'video_content'):
                VideoLesson.objects.create(
                    lesson=obj,
                    vimeo_video_id='',
                    video_duration=0
                )
            elif obj.lesson_type == 'text' and not hasattr(obj, 'text_content'):
                TextLesson.objects.create(
                    lesson=obj,
                    content=''
                )
            elif obj.lesson_type == 'quiz' and not hasattr(obj, 'quiz_content'):
                QuizLesson.objects.create(lesson=obj)
            elif obj.lesson_type == 'assignment' and not hasattr(obj, 'assignment_content'):
                AssignmentLesson.objects.create(
                    lesson=obj,
                    instructions=''
                )


@admin.register(VideoLesson)
class VideoLessonAdmin(admin.ModelAdmin):
    list_display = ('lesson', 'vimeo_video_id', 'video_duration_display', 'completion_threshold')
    search_fields = ('lesson__title', 'vimeo_video_id')
    list_filter = ('lesson__module__course',)  # ← ИСПРАВЛЕНО

    fieldsets = (
        ('Урок', {
            'fields': ('lesson',)
        }),
        ('Видео настройки', {
            'fields': ('vimeo_video_id', 'video_duration', 'completion_threshold')
        }),
        ('Таймкоды', {
            'fields': ('timecodes',),
            'classes': ('collapse',),
            'description': 'JSON формат: [{"time": "00:30", "title": "Введение"}]'
        }),
        ('Дополнительно', {
            'fields': ('allow_speed_control', 'allow_download'),
            'classes': ('collapse',)
        }),
    )

    def video_duration_display(self, obj):
        """Отображение длительности в читаемом формате"""
        if obj.video_duration:
            minutes = obj.video_duration // 60
            seconds = obj.video_duration % 60
            return f"{minutes}:{seconds:02d}"
        return '-'

    video_duration_display.short_description = 'Длительность'


@admin.register(TextLesson)
class TextLessonAdmin(admin.ModelAdmin):
    list_display = ('lesson', 'word_count', 'estimated_reading_time')
    search_fields = ('lesson__title', 'content')
    list_filter = ('lesson__module__course',)  # ← ИСПРАВЛЕНО

    fieldsets = (
        ('Урок', {
            'fields': ('lesson',)
        }),
        ('Контент', {
            'fields': ('content', 'estimated_reading_time', 'word_count')
        }),
    )

    readonly_fields = ('word_count',)


@admin.register(QuizLesson)
class QuizLessonAdmin(admin.ModelAdmin):
    list_display = ('lesson', 'passing_score', 'max_attempts', 'retry_delay_hours', 'get_questions_count')
    search_fields = ('lesson__title',)
    list_filter = ('lesson__module__course',)  # ← ИСПРАВЛЕНО
    inlines = [QuizQuestionInline]

    fieldsets = (
        ('Урок', {
            'fields': ('lesson',)
        }),
        ('Настройки прохождения', {
            'fields': ('passing_score', 'max_attempts', 'retry_delay_hours', 'time_limit_minutes')
        }),
        ('Отображение результатов', {
            'fields': ('show_correct_answers', 'show_incorrect_only', 'show_score_immediately'),
            'classes': ('collapse',)
        }),
        ('Рандомизация', {
            'fields': ('shuffle_questions', 'shuffle_answers'),
            'classes': ('collapse',)
        }),
    )

    def get_questions_count(self, obj):
        """Количество вопросов"""
        count = obj.get_total_questions()
        return format_html('<b>{}</b>', count)

    get_questions_count.short_description = 'Вопросов'


@admin.register(QuizQuestion)
class QuizQuestionAdmin(admin.ModelAdmin):
    list_display = ('get_question_title', 'quiz', 'question_type', 'points', 'order', 'is_active')
    list_filter = ('quiz__lesson__module__course', 'question_type', 'is_active')  # ← ИСПРАВЛЕНО
    search_fields = ('question_text', 'quiz__lesson__title')
    inlines = [QuizAnswerInline]

    fieldsets = (
        ('Основное', {
            'fields': ('quiz', 'order', 'question_type', 'is_active')
        }),
        ('Вопрос', {
            'fields': ('question_text', 'points')
        }),
        ('Пояснение', {
            'fields': ('explanation',),
            'classes': ('collapse',)
        }),
    )

    def get_question_title(self, obj):
        """Отображение вопроса"""
        return f"{obj.order}. {obj.question_text[:50]}..."

    get_question_title.short_description = 'Вопрос'


@admin.register(AssignmentLesson)
class AssignmentLessonAdmin(admin.ModelAdmin):
    list_display = ('lesson', 'require_text', 'require_file', 'deadline', 'max_score', 'allow_resubmission')
    search_fields = ('lesson__title', 'instructions')
    list_filter = ('lesson__module__course', 'require_text', 'require_file', 'allow_resubmission')  # ← ИСПРАВЛЕНО

    fieldsets = (
        ('Урок', {
            'fields': ('lesson',)
        }),
        ('Инструкции', {
            'fields': ('instructions',)
        }),
        ('Требования к ответу', {
            'fields': ('require_text', 'require_file'),
            'description': 'Выберите что студент должен заполнить обязательно'
        }),
        ('Оценка', {
            'fields': ('max_score',)
        }),
        ('Дедлайн', {
            'fields': ('deadline', 'allow_late_submission', 'late_penalty_percent'),
            'classes': ('collapse',)
        }),
        ('Пересдача', {
            'fields': ('allow_resubmission', 'max_resubmissions'),
            'classes': ('collapse',)
        }),
        ('Файлы', {
            'fields': ('allowed_file_types', 'max_file_size_mb'),
            'classes': ('collapse',)
        }),
    )


@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'get_assignment_title',
        'submission_number',
        'get_status',
        'score',
        'is_late',
        'submitted_at'
    )
    list_filter = ('status', 'is_late', 'assignment__lesson__module__course', 'submitted_at')  # ← ИСПРАВЛЕНО
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'assignment__lesson__title')
    readonly_fields = ('created_at', 'submitted_at', 'reviewed_at', 'is_late')
    inlines = [AssignmentCommentInline]

    fieldsets = (
        ('Информация', {
            'fields': ('assignment', 'user', 'submission_number', 'status', 'is_late')
        }),
        ('Работа студента', {
            'fields': ('submission_text', 'submission_file')
        }),
        ('Даты', {
            'fields': ('created_at', 'submitted_at', 'reviewed_at'),
            'classes': ('collapse',)
        }),
        ('Проверка', {
            'fields': ('score', 'feedback', 'reviewed_by'),
            'classes': ('collapse',)
        }),
    )

    def get_assignment_title(self, obj):
        """Название задания"""
        return obj.assignment.lesson.title

    get_assignment_title.short_description = 'Задание'

    def get_status(self, obj):
        """Статус с цветом"""
        colors = {
            'draft': 'gray',
            'submitted': 'blue',
            'in_review': 'orange',
            'revision_requested': 'purple',
            'approved': 'green',
            'rejected': 'red',
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )

    get_status.short_description = 'Статус'

    def save_model(self, request, obj, form, change):
        """Автоматически установить проверяющего"""
        if change and 'status' in form.changed_data:
            if obj.status in ['approved', 'rejected', 'revision_requested']:
                if not obj.reviewed_by:
                    obj.reviewed_by = request.user
                if not obj.reviewed_at:
                    obj.reviewed_at = timezone.now()
        super().save_model(request, obj, form, change)


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'get_quiz_title',
        'attempt_number',
        'get_status',
        'score_percentage',
        'correct_answers',
        'total_questions',
        'started_at'
    )
    list_filter = ('status', 'quiz__lesson__module__course', 'started_at')  # ← ИСПРАВЛЕНО
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'quiz__lesson__title')
    readonly_fields = ('started_at', 'completed_at', 'expires_at', 'can_retry_at')

    fieldsets = (
        ('Информация', {
            'fields': ('user', 'quiz', 'attempt_number', 'status')
        }),
        ('Результаты', {
            'fields': ('total_questions', 'correct_answers', 'total_points', 'earned_points', 'score_percentage')
        }),
        ('Даты', {
            'fields': ('started_at', 'completed_at', 'expires_at', 'can_retry_at')
        }),
    )

    def get_quiz_title(self, obj):
        """Название теста"""
        return obj.quiz.lesson.title

    get_quiz_title.short_description = 'Тест'

    def get_status(self, obj):
        """Статус с цветом"""
        colors = {
            'in_progress': 'blue',
            'completed': 'gray',
            'passed': 'green',
            'failed': 'red',
            'expired': 'orange',
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )

    get_status.short_description = 'Статус'


@admin.register(VideoProgress)
class VideoProgressAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'get_video_title',
        'watch_percentage',
        'is_completed',
        'watch_count',
        'last_watched_at'
    )
    list_filter = ('is_completed', 'video_lesson__lesson__module__course', 'last_watched_at')  # ← ИСПРАВЛЕНО
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'video_lesson__lesson__title')
    readonly_fields = ('first_watched_at', 'last_watched_at', 'completed_at')

    fieldsets = (
        ('Информация', {
            'fields': ('user', 'video_lesson')
        }),
        ('Прогресс', {
            'fields': ('current_position', 'watch_percentage', 'is_completed')
        }),
        ('Статистика', {
            'fields': ('total_watch_time', 'watch_count')
        }),
        ('Даты', {
            'fields': ('first_watched_at', 'last_watched_at', 'completed_at')
        }),
    )

    def get_video_title(self, obj):
        """Название видео урока"""
        return obj.video_lesson.lesson.title

    get_video_title.short_description = 'Видео урок'


@admin.register(LessonMaterial)
class LessonMaterialAdmin(admin.ModelAdmin):
    list_display = ('title', 'lesson', 'get_type', 'file_size_display', 'order', 'created_at')
    list_filter = ('lesson__module__course', 'file_type', 'created_at')  # ← ИСПРАВЛЕНО
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
    list_display = ('user', 'course', 'get_progress_display', 'enrolled_at', 'last_activity_at')
    list_filter = ('course', 'enrolled_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'course__title')
    readonly_fields = ('enrolled_at', 'get_progress_display', 'completed_lessons_count', 'progress_percentage',
                       'last_activity_at')

    fieldsets = (
        ('Информация', {
            'fields': ('user', 'course', 'enrolled_at', 'last_activity_at')
        }),
        ('Прогресс', {
            'fields': ('get_progress_display', 'completed_lessons_count', 'progress_percentage')
        }),
    )

    def get_progress_display(self, obj):
        """Отображение прогресса с цветом"""
        if obj.pk:
            progress = obj.get_progress_percentage()
            # ← ИСПРАВЛЕНИЕ: явное преобразование в float
            progress_value = float(progress) if progress else 0

            color = 'green' if progress_value == 100 else 'orange' if progress_value > 50 else 'red'

            # Форматируем число отдельно
            progress_str = f"{progress_value:.1f}"

            return format_html(
                '<div style="background: {}; color: white; padding: 5px 10px; border-radius: 5px; text-align: center; width: 80px;">'
                '<b>{}%</b></div>',
                color, progress_str  # ← Передаем строку, а не число
            )
        return '-'

    get_progress_display.short_description = 'Прогресс'


@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_lesson_info', 'is_completed', 'started_at', 'completed_at')
    list_filter = ('is_completed', 'lesson__module__course', 'started_at', 'completed_at')  # ← ИСПРАВЛЕНО
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'lesson__title')
    readonly_fields = ('started_at', 'completed_at', 'completion_data')

    fieldsets = (
        ('Информация', {
            'fields': ('user', 'lesson', 'is_completed')
        }),
        ('Даты', {
            'fields': ('started_at', 'completed_at', 'available_at')
        }),
        ('Данные завершения', {
            'fields': ('completion_data',),
            'classes': ('collapse',)
        }),
    )

    def get_lesson_info(self, obj):
        """Информация об уроке"""
        return format_html(
            '<b>{}</b><br><small>Модуль: {} | Урок: {}</small>',
            obj.lesson.module.course.title,
            obj.lesson.module.title,
            obj.lesson.title
        )

    get_lesson_info.short_description = 'Курс / Модуль / Урок'