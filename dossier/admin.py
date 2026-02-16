from django.contrib import admin

from .models import StudentDossier, InstructorDossier


@admin.register(StudentDossier)
class StudentDossierAdmin(admin.ModelAdmin):
    list_display = (
        'get_full_name', 'course_title', 'group_name',
        'certificate_number', 'final_score', 'graduated_at',
    )
    list_filter = ('course_title', 'graduated_at')
    search_fields = (
        'first_name', 'last_name', 'iin',
        'email', 'certificate_number',
    )
    readonly_fields = (
        'dossier_created_at',
        'lessons_history', 'quizzes_history',
        'assignments_history', 'modules_history',
    )
    fieldsets = (
        ('Личные данные', {
            'fields': (
                'user', 'graduate',
                'first_name', 'last_name', 'middle_name',
                'email', 'iin', 'phone',
            ),
        }),
        ('Обучение', {
            'fields': (
                'course_title', 'course_label',
                'group_name', 'instructor_name', 'instructor_email',
            ),
        }),
        ('Сертификат', {
            'fields': ('certificate_number',),
        }),
        ('Даты', {
            'fields': (
                'enrolled_at', 'completed_at',
                'graduated_at', 'dossier_created_at',
            ),
        }),
        ('Результаты', {
            'fields': (
                'final_score', 'total_lessons_completed',
                'total_study_days', 'average_quiz_score',
            ),
        }),
        ('История (JSON)', {
            'classes': ('collapse',),
            'fields': (
                'lessons_history', 'quizzes_history',
                'assignments_history', 'modules_history',
            ),
        }),
    )


@admin.register(InstructorDossier)
class InstructorDossierAdmin(admin.ModelAdmin):
    list_display = (
        'get_full_name', 'role', 'total_groups_led',
        'total_students_taught', 'total_graduates', 'last_updated_at',
    )
    list_filter = ('role',)
    search_fields = ('first_name', 'last_name', 'email')
    readonly_fields = (
        'dossier_created_at', 'last_updated_at',
        'groups_history', 'reviews_summary',
    )
    fieldsets = (
        ('Личные данные', {
            'fields': (
                'user',
                'first_name', 'last_name', 'middle_name',
                'email', 'phone',
            ),
        }),
        ('Роль', {
            'fields': ('role', 'role_assigned_at'),
        }),
        ('Статистика', {
            'fields': (
                'total_groups_led', 'total_students_taught', 'total_graduates',
                'total_assignments_reviewed', 'total_assignments_passed',
                'total_assignments_rejected', 'average_score_given',
            ),
        }),
        ('Даты', {
            'fields': ('registered_at', 'dossier_created_at', 'last_updated_at'),
        }),
        ('История (JSON)', {
            'classes': ('collapse',),
            'fields': ('groups_history', 'reviews_summary'),
        }),
    )
