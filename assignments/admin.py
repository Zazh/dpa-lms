from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Avg
from content.models import Lesson
from .models import AssignmentLesson, AssignmentSubmission, AssignmentComment


class AssignmentSubmissionInline(admin.TabularInline):
    """Inline для сдач задания"""
    model = AssignmentSubmission
    extra = 0
    fields = ['user', 'submission_number', 'status', 'score', 'submitted_at']
    readonly_fields = ['user', 'submission_number', 'submitted_at']
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(AssignmentLesson)
class AssignmentLessonAdmin(admin.ModelAdmin):
    list_display = ['lesson', 'require_text_badge', 'require_file_badge', 'max_score', 'deadline_days',
                    'submissions_info']
    search_fields = ['lesson__title', 'instructions']
    readonly_fields = ['submissions_count', 'pending_count', 'average_score']

    fieldsets = (
        ('Связь с уроком', {
            'fields': ('lesson',)
        }),
        ('Инструкции', {
            'fields': ('instructions',)
        }),
        ('Требования', {
            'fields': ('require_text', 'require_file', 'max_score', 'deadline_days')
        }),
        ('Настройки', {
            'fields': ('allow_late_submission', 'allow_resubmission')
        }),
        ('Статистика', {
            'fields': ('submissions_count', 'pending_count', 'average_score'),
            'classes': ('collapse',)
        }),
    )

    inlines = [AssignmentSubmissionInline]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Показывать только уроки с типом 'assignment'"""
        if db_field.name == "lesson":
            kwargs["queryset"] = Lesson.objects.filter(lesson_type='assignment')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def require_text_badge(self, obj):
        return '✅ Да' if obj.require_text else '❌ Нет'

    require_text_badge.short_description = 'Текст'

    def require_file_badge(self, obj):
        return '✅ Да' if obj.require_file else '❌ Нет'

    require_file_badge.short_description = 'Файл'

    def submissions_info(self, obj):
        if obj.pk:
            total = obj.get_submissions_count()
            pending = obj.get_pending_count()
            return f'📝 {total} | 🔍 {pending}'
        return '-'

    submissions_info.short_description = 'Сдачи'

    def submissions_count(self, obj):
        if obj.pk:
            return f'📝 {obj.get_submissions_count()}'
        return 0

    submissions_count.short_description = 'Всего сдач'

    def pending_count(self, obj):
        if obj.pk:
            return f'🔍 {obj.get_pending_count()}'
        return 0

    pending_count.short_description = 'На проверке'

    def average_score(self, obj):
        if obj.pk:
            return f'⭐ {obj.get_average_score()}'
        return 0

    average_score.short_description = 'Средний балл'


class AssignmentCommentInline(admin.TabularInline):
    """Inline для комментариев"""
    model = AssignmentComment
    extra = 1
    fields = ['author', 'message', 'is_instructor', 'is_read', 'created_at']
    readonly_fields = ['created_at']
    ordering = ['created_at']


@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = ['user_info', 'assignment_short', 'submission_number', 'status_badge', 'score_display',
                    'submitted_at', 'comments_count']
    list_filter = ['status', 'assignment__lesson__module__course', 'submitted_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'assignment__lesson__title']
    readonly_fields = ['user', 'assignment', 'submission_number', 'submitted_at', 'reviewed_at', 'file_link',
                       'score_percentage', 'comments_count']
    date_hierarchy = 'submitted_at'

    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'assignment', 'submission_number', 'status')
        }),
        ('Ответ студента', {
            'fields': ('submission_text', 'submission_file', 'file_link', 'submitted_at')
        }),
        ('Проверка', {
            'fields': ('score', 'score_percentage', 'feedback', 'reviewed_by', 'reviewed_at')
        }),
        ('Дополнительно', {
            'fields': ('comments_count',),
            'classes': ('collapse',)
        }),
    )

    inlines = [AssignmentCommentInline]
    actions = ['mark_in_review_action', 'mark_passed_action', 'mark_needs_revision_action']

    def user_info(self, obj):
        return f"{obj.user.get_full_name()} ({obj.user.email})"

    user_info.short_description = 'Студент'

    def assignment_short(self, obj):
        return obj.assignment.lesson.title[:50]

    assignment_short.short_description = 'Задание'

    def status_badge(self, obj):
        colors = {
            'waiting': '#6c757d',
            'in_review': '#ffc107',
            'needs_revision': '#17a2b8',
            'failed': '#dc3545',
            'passed': '#28a745',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            colors.get(obj.status, '#6c757d'),
            obj.get_status_display()
        )

    status_badge.short_description = 'Статус'

    def score_display(self, obj):
        if obj.score is not None:
            percentage = obj.get_score_percentage()
            return f'⭐ {obj.score}/{obj.assignment.max_score} ({percentage}%)'
        return '-'

    score_display.short_description = 'Балл'

    def score_percentage(self, obj):
        return f'{obj.get_score_percentage()}%'

    score_percentage.short_description = 'Процент'

    def file_link(self, obj):
        if obj.submission_file:
            return format_html(
                '<a href="{}" target="_blank">📎 Скачать файл</a>',
                obj.submission_file.url
            )
        return 'Нет файла'

    file_link.short_description = 'Файл'

    def comments_count(self, obj):
        if obj.pk:
            return f'💬 {obj.get_comments_count()}'
        return 0

    comments_count.short_description = 'Комментариев'

    def mark_in_review_action(self, request, queryset):
        """Взять на проверку"""
        count = 0
        for submission in queryset.filter(status='waiting'):
            submission.mark_in_review(request.user)
            count += 1
        self.message_user(request, f'🔍 Взято на проверку: {count}')

    mark_in_review_action.short_description = '🔍 Взять на проверку'

    def mark_passed_action(self, request, queryset):
        """Зачесть (с максимальным баллом)"""
        count = 0
        for submission in queryset.filter(status__in=['in_review', 'needs_revision']):
            submission.mark_passed(
                instructor=request.user,
                score=submission.assignment.max_score,
                feedback='Отличная работа!'
            )
            count += 1
        self.message_user(request, f'✅ Зачтено: {count}')

    mark_passed_action.short_description = '✅ Зачесть (макс. балл)'

    def mark_needs_revision_action(self, request, queryset):
        """Отправить на доработку"""
        count = 0
        for submission in queryset.filter(status='in_review'):
            submission.mark_needs_revision(
                instructor=request.user,
                feedback='Требуется доработка. См. комментарии.'
            )
            count += 1
        self.message_user(request, f'✏️ Отправлено на доработку: {count}')

    mark_needs_revision_action.short_description = '✏️ На доработку'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(AssignmentComment)
class AssignmentCommentAdmin(admin.ModelAdmin):
    list_display = ['author_info', 'submission_short', 'message_short', 'author_type_badge', 'is_read_badge',
                    'created_at']
    list_filter = ['is_instructor', 'is_read', 'created_at']
    search_fields = ['author__email', 'message', 'submission__user__email']
    readonly_fields = ['submission', 'author', 'created_at']
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Основная информация', {
            'fields': ('submission', 'author', 'is_instructor')
        }),
        ('Комментарий', {
            'fields': ('message', 'is_read', 'created_at')
        }),
    )

    def author_info(self, obj):
        icon = '👨‍🏫' if obj.is_instructor else '👨‍🎓'
        return f'{icon} {obj.author.get_full_name()}'

    author_info.short_description = 'Автор'

    def submission_short(self, obj):
        return f"{obj.submission.user.email} - {obj.submission.assignment.lesson.title[:30]}"

    submission_short.short_description = 'Сдача'

    def message_short(self, obj):
        return obj.message[:60] + '...' if len(obj.message) > 60 else obj.message

    message_short.short_description = 'Сообщение'

    def author_type_badge(self, obj):
        if obj.is_instructor:
            return format_html('<span style="color: #007bff; font-weight: bold;">👨‍🏫 Преподаватель</span>')
        return format_html('<span style="color: #28a745;">👨‍🎓 Студент</span>')

    author_type_badge.short_description = 'Тип'

    def is_read_badge(self, obj):
        if obj.is_read:
            return '✅ Прочитано'
        return format_html('<span style="color: #dc3545; font-weight: bold;">📬 Новое</span>')

    is_read_badge.short_description = 'Статус'

    def has_add_permission(self, request):
        return True  # Преподаватели могут оставлять комментарии

    def has_delete_permission(self, request, obj=None):
        # Можно удалить только свои комментарии или суперюзер
        if request.user.is_superuser:
            return True
        if obj and obj.author == request.user:
            return True
        return False