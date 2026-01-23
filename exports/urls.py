from django.urls import path
from .views import QuizResultPDFView

app_name = 'exports'

urlpatterns = [
    path(
        'quiz-results/<int:attempt_id>/',
        QuizResultPDFView.as_view(),
        name='quiz-result-pdf'
    ),
]