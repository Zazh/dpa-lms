from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from quizzes.models import QuizAttempt
from .services import QuizResultPDFService


class QuizResultPDFView(APIView):
    """
    GET /api/exports/quiz-results/{attempt_id}/

    Скачать PDF с результатами теста
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, attempt_id):
        attempt = get_object_or_404(
            QuizAttempt.objects.select_related(
                'quiz__lesson__module__course',
                'user'
            ),
            id=attempt_id,
            user=request.user,
            status='completed'
        )

        service = QuizResultPDFService()

        try:
            pdf_content = service.generate(attempt)
        except Exception as e:
            return Response(
                {'error': f'Ошибка генерации PDF: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        filename = f"quiz_result_{attempt.id}.pdf"

        response = HttpResponse(pdf_content, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        return response


@staff_member_required
def preview_certificate(request):
    """
    Превью сертификата для разработки.

    GET /api/exports/preview/certificate/
    GET /api/exports/preview/certificate/?stamp=1
    GET /api/exports/preview/certificate/?type=attended
    """
    from datetime import date
    from .services import CertificatePDFService

    certificate_type = request.GET.get('type', 'certificate')
    with_stamp = request.GET.get('stamp') == '1'

    # Определяем тексты в зависимости от типа
    if certificate_type == 'attended':
        document_title = 'СПРАВКА'
        completion_text = 'прослушал(а) курс'
    else:
        document_title = 'СЕРТИФИКАТ'
        completion_text = 'успешно завершил(–а) курс'

    class MockCertificate:
        pass

    mock = MockCertificate()
    mock.holder_name = 'Алдакуатов Елдос'
    mock.course_title = 'Первоначальная теоретическая подготовка операторов БАС Категории 2'
    mock.number = 'KZ2025A1B2C3'
    mock.issued_at = date.today()
    mock.group_name = 'Группа А-101'
    mock.document_title = document_title
    mock.completion_text = completion_text
    mock.issue_date_label = 'Дата выдачи:'
    mock.stamp_css_class = 'stamp-img-1'
    mock.signature_css_class = 'aft-img-1'
    mock.signer_name = 'Худайбергенова П.Т.'
    mock.signer_position = 'Генеральный директор<br>ТОО "Aerial Solutions"'

    service = CertificatePDFService()
    pdf_bytes = service.generate_from_certificate(mock, with_stamp=with_stamp)

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="certificate_preview.pdf"'
    return response