from django.urls import path
from . import views

app_name = 'backoffice'

urlpatterns = [
    # Главная
    path('', views.dashboard, name='dashboard'),

    # Авторизация
    path('login/', views.backoffice_login, name='login'),
    path('logout/', views.backoffice_logout, name='logout'),

    # Группы
    path('groups/', views.groups_list, name='groups_list'),
    path('groups/create/', views.group_create, name='group_create'),
    path('groups/<int:group_id>/', views.group_detail, name='group_detail'),
    path('groups/<int:group_id>/edit/', views.group_edit, name='group_edit'),

    # Прогресс студента
    path('students/<int:user_id>/progress/<int:group_id>/', views.student_progress, name='student_progress'),

    # Проверка ДЗ
    path('assignments/', views.assignments_check, name='assignments_check'),
    path('assignments/<int:submission_id>/', views.assignment_detail, name='assignment_detail'),

    # Доступ запрещен
    path('no-access/', views.no_access, name='no_access'),

    # Результаты тестов
    path('quizzes/', views.quiz_attempts_list, name='quiz_attempts_list'),
    path('quizzes/<int:attempt_id>/', views.quiz_attempt_detail, name='quiz_attempt_detail'),
    path('quizzes/<int:attempt_id>/export-pdf/', views.export_quiz_attempt_pdf, name='export_quiz_attempt_pdf'),

    # Выпускники
    path('graduates/', views.graduates_list, name='graduates_list'),
    path('graduates/<int:graduate_id>/', views.graduate_detail, name='graduate_detail'),
    path('graduates/bulk-action/', views.graduates_bulk_action, name='graduates_bulk_action'),


    # Досье студентов
    path('dossier/students/', views.student_dossiers_list, name='student_dossiers_list'),
    path('dossier/students/<int:dossier_id>/', views.student_dossier_detail, name='student_dossier_detail'),

    # Досье инструкторов
    path('dossier/instructors/', views.instructor_dossiers_list, name='instructor_dossiers_list'),
    path('dossier/instructors/<int:dossier_id>/', views.instructor_dossier_detail, name='instructor_dossier_detail'),

    # Экспорт PDF
    path('dossier/students/<int:dossier_id>/quiz/<int:quiz_index>/export-pdf/', views.export_dossier_quiz_pdf, name='export_dossier_quiz_pdf'),
    path('dossier/students/<int:dossier_id>/certificate/no-stamp/', views.export_dossier_certificate_no_stamp, name='export_dossier_certificate_no_stamp'),
    path('dossier/students/<int:dossier_id>/certificate/with-stamp/', views.export_dossier_certificate_with_stamp, name='export_dossier_certificate_with_stamp'),
]