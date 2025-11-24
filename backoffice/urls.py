from django.urls import path
from . import views

app_name = 'backoffice'

urlpatterns = [
    # Главная
    path('', views.dashboard, name='dashboard'),

    # Группы
    path('groups/', views.groups_list, name='groups_list'),
    path('groups/<int:group_id>/', views.group_detail, name='group_detail'),

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

]