from django.urls import path
from . import api_views

app_name = 'quizzes'

urlpatterns = [
    # Начать тест
    path('<int:quiz_id>/start/', api_views.start_quiz, name='start_quiz'),

    # Отправить ответы
    path('attempts/<int:attempt_id>/submit/', api_views.submit_quiz, name='submit_quiz'),

    # История попыток
    path('attempts/', api_views.user_quiz_attempts, name='user_attempts'),

    # Детали попытки
    path('attempts/<int:attempt_id>/', api_views.quiz_attempt_detail, name='attempt_detail'),
]