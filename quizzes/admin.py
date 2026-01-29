from content.models import Lesson
from django.contrib import admin
from django.utils.html import format_html
from django.core.exceptions import PermissionDenied

from .models import QuizLesson, QuizQuestion, QuizAnswer, QuizAttempt, QuizResponse


class QuizAnswerInline(admin.TabularInline):
    """Inline для вариантов ответов"""
    model = QuizAnswer
    extra = 2
    fields = ['order', 'answer_text', 'is_correct', 'has_responses']
    readonly_fields = ['has_responses']
    ordering = ['order']

    def has_responses(self, obj):
        """Показать есть ли ответы студентов"""
        if not obj.pk:
            return '-'
        # Проверяем что это QuizAnswer, а не родительский объект
        if not hasattr(obj, 'selected_by'):
            return '-'
        count = obj.selected_by.count()
        if count > 0:
            return format_html(
                '<span style="color: red;">🔒 {} ответов</span>',
                count
            )
        return '✅ Можно удалить'

    has_responses.short_description = 'Использован'

    def has_delete_permission(self, request, obj=None):
        """Запретить удаление если есть ответы студентов"""
        if obj and hasattr(obj, 'selected_by') and obj.selected_by.exists():
            return False
        return super().has_delete_permission(request, obj)


@admin.register(QuizQuestion)
class QuizQuestionAdmin(admin.ModelAdmin):
    list_display = ['question_text_short', 'quiz', 'type_badge', 'points', 'order', 'answers_info']
    list_filter = ['quiz__lesson__module__course', 'question_type']
    search_fields = ['question_text', 'quiz__lesson__title']
    readonly_fields = ['created_at', 'updated_at', 'answers_count', 'correct_answers_count']

    fieldsets = (
        ('Основная информация', {
            'fields': ('quiz', 'question_type', 'question_text', 'explanation', 'points', 'order')
        }),
        ('Статистика', {
            'fields': ('answers_count', 'correct_answers_count'),
            'classes': ('collapse',)
        }),
        ('Системная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    inlines = [QuizAnswerInline]

    def question_text_short(self, obj):
        return obj.question_text[:70] + '...' if len(obj.question_text) > 70 else obj.question_text

    question_text_short.short_description = 'Вопрос'

    def type_badge(self, obj):
        colors = {
            'single_choice': '#007bff',
            'multiple_choice': '#28a745',
            'true_false': '#ffc107',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            colors.get(obj.question_type, '#6c757d'),
            obj.get_question_type_display()
        )

    type_badge.short_description = 'Тип'

    def answers_info(self, obj):
        total = obj.get_answers_count()
        correct = obj.get_correct_answers_count()
        return f'✅ {correct} / 📝 {total}'

    answers_info.short_description = 'Ответы'

    def answers_count(self, obj):
        if obj.pk:
            return obj.get_answers_count()
        return 0

    answers_count.short_description = 'Всего ответов'

    def correct_answers_count(self, obj):
        if obj.pk:
            return obj.get_correct_answers_count()
        return 0

    correct_answers_count.short_description = 'Правильных ответов'


class QuizQuestionInline(admin.TabularInline):
    """Inline для вопросов теста"""
    model = QuizQuestion
    extra = 0
    fields = ['order', 'question_type', 'question_text', 'points']
    ordering = ['order']
    show_change_link = True


@admin.register(QuizLesson)
class QuizLessonAdmin(admin.ModelAdmin):
    list_display = ['lesson', 'passing_score', 'max_attempts', 'time_limit', 'questions_count', 'total_points']
    search_fields = ['lesson__title']
    readonly_fields = ['questions_count', 'total_points']

    fieldsets = (
        ('Связь с уроком', {
            'fields': ('lesson',)
        }),
        ('Настройки прохождения', {
            'fields': ('passing_score', 'max_attempts', 'retry_delay_minutes', 'time_limit_minutes')
        }),
        ('Настройки отображения', {
            'fields': ('show_correct_answers', 'shuffle_questions', 'shuffle_answers')
        }),
        ('Статистика', {
            'fields': ('questions_count', 'total_points'),
            'classes': ('collapse',)
        }),
    )

    inlines = [QuizQuestionInline]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Показывать только уроки с типом 'quiz'"""
        if db_field.name == "lesson":
            kwargs["queryset"] = Lesson.objects.filter(lesson_type='quiz')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def time_limit(self, obj):
        if obj.time_limit_minutes > 0:
            return f'⏰ {obj.time_limit_minutes} мин'
        return '∞ Без ограничения'

    time_limit.short_description = 'Лимит времени'

    def questions_count(self, obj):
        if obj.pk:
            return f'❓ {obj.get_questions_count()}'
        return 0

    questions_count.short_description = 'Вопросов'

    def total_points(self, obj):
        if obj.pk:
            return f'⭐ {obj.get_total_points()}'
        return 0

    total_points.short_description = 'Всего баллов'


class QuizResponseInline(admin.TabularInline):
    """Inline для ответов попытки"""
    model = QuizResponse
    extra = 0
    fields = ['question', 'is_correct', 'points_earned', 'selected_answers_display']
    readonly_fields = ['question', 'is_correct', 'points_earned', 'selected_answers_display']
    can_delete = False

    def selected_answers_display(self, obj):
        if obj.pk:
            answers = obj.selected_answers.all()
            return ', '.join([a.answer_text[:50] for a in answers])
        return '-'

    selected_answers_display.short_description = 'Выбранные ответы'

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ['user', 'quiz', 'attempt_number', 'status_badge', 'score_badge', 'passed_badge', 'started_at',
                    'duration']
    list_filter = ['status', 'quiz__lesson__module__course', 'started_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'quiz__lesson__title']
    readonly_fields = ['user', 'quiz', 'attempt_number', 'status', 'score_percentage', 'started_at', 'completed_at',
                       'duration_display']
    date_hierarchy = 'started_at'

    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'quiz', 'attempt_number', 'status')
        }),
        ('Результаты', {
            'fields': ('score_percentage', 'started_at', 'completed_at', 'duration_display')
        }),
    )

    inlines = [QuizResponseInline]

    def status_badge(self, obj):
        colors = {
            'in_progress': '#ffc107',
            'completed': '#28a745',
            'timeout': '#dc3545',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            colors.get(obj.status, '#6c757d'),
            obj.get_status_display()
        )

    status_badge.short_description = 'Статус'

    def score_badge(self, obj):
        if obj.score_percentage is not None:
            return f'⭐ {obj.score_percentage}%'
        return '-'

    score_badge.short_description = 'Результат'

    def passed_badge(self, obj):
        if obj.status == 'completed':
            if obj.is_passed():
                return format_html('<span style="color: #28a745; font-weight: bold;">✅ Пройден</span>')
            return format_html('<span style="color: #dc3545; font-weight: bold;">❌ Не пройден</span>')
        return '-'

    passed_badge.short_description = 'Пройден'

    def duration(self, obj):
        if obj.pk:
            seconds = obj.get_duration_seconds()
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f'⏱️ {minutes}:{secs:02d}'
        return '-'

    duration.short_description = 'Длительность'

    def duration_display(self, obj):
        if obj.pk:
            seconds = obj.get_duration_seconds()
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f'{minutes} мин {secs} сек'
        return '-'

    duration_display.short_description = 'Длительность'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(QuizAnswer)
class QuizAnswerAdmin(admin.ModelAdmin):
    list_display = ['answer_text_short', 'question_short', 'is_correct_badge', 'order', 'responses_count']
    list_filter = ['is_correct', 'question__quiz__lesson__module__course']
    search_fields = ['answer_text', 'question__question_text']

    def answer_text_short(self, obj):
        return obj.answer_text[:60] + '...' if len(obj.answer_text) > 60 else obj.answer_text

    answer_text_short.short_description = 'Ответ'

    def question_short(self, obj):
        return obj.question.question_text[:50] + '...' if len(
            obj.question.question_text) > 50 else obj.question.question_text

    question_short.short_description = 'Вопрос'

    def is_correct_badge(self, obj):
        if obj.is_correct:
            return format_html('<span style="color: #28a745; font-weight: bold;">✅ Правильный</span>')
        return format_html('<span style="color: #dc3545;">❌ Неправильный</span>')

    is_correct_badge.short_description = 'Правильность'

    def responses_count(self, obj):
        count = obj.selected_by.count()
        if count > 0:
            return format_html('<span style="color: red;">🔒 {}</span>', count)
        return '✅ 0'

    responses_count.short_description = 'Выбран студентами'

    def delete_model(self, request, obj):
        if obj.selected_by.exists():
            raise PermissionDenied(
                'Нельзя удалить вариант ответа — его выбирали студенты'
            )
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            if obj.selected_by.exists():
                raise PermissionDenied(
                    f'Нельзя удалить "{obj.answer_text[:30]}..." — его выбирали студенты'
                )
        super().delete_queryset(request, queryset)


@admin.register(QuizResponse)
class QuizResponseAdmin(admin.ModelAdmin):
    list_display = ['attempt_info', 'question_short', 'is_correct_badge', 'points_earned', 'answered_at']
    list_filter = ['is_correct', 'answered_at']
    search_fields = ['attempt__user__email', 'question__question_text']
    readonly_fields = ['attempt', 'question', 'selected_answers_display', 'is_correct', 'points_earned', 'answered_at']
    date_hierarchy = 'answered_at'

    fieldsets = (
        ('Основная информация', {
            'fields': ('attempt', 'question')
        }),
        ('Ответ', {
            'fields': ('selected_answers_display', 'is_correct', 'points_earned', 'answered_at')
        }),
    )

    def attempt_info(self, obj):
        return f"{obj.attempt.user.email} - Попытка #{obj.attempt.attempt_number}"

    attempt_info.short_description = 'Попытка'

    def question_short(self, obj):
        return obj.question.question_text[:50] + '...' if len(
            obj.question.question_text) > 50 else obj.question.question_text

    question_short.short_description = 'Вопрос'

    def is_correct_badge(self, obj):
        if obj.is_correct:
            return format_html('<span style="color: #28a745; font-weight: bold;">✅ Правильно</span>')
        return format_html('<span style="color: #dc3545; font-weight: bold;">❌ Неправильно</span>')

    is_correct_badge.short_description = 'Результат'

    def selected_answers_display(self, obj):
        if obj.pk:
            answers = obj.selected_answers.all()
            result = []
            for answer in answers:
                icon = '✅' if answer.is_correct else '❌'
                result.append(f'{icon} {answer.answer_text}')
            return format_html('<br>'.join(result))
        return '-'

    selected_answers_display.short_description = 'Выбранные ответы'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser