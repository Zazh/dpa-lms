from django.urls import path
from .views import QuizResultPDFView, preview_certificate

app_name = 'exports'

urlpatterns = [
    path(
        'quiz-results/<int:attempt_id>/',
        QuizResultPDFView.as_view(),
        name='quiz-result-pdf'
    ),

    # Превью для разработки (только staff)
        path(
            'preview/certificate/',
            preview_certificate,
            name='preview-certificate'
        ),
]