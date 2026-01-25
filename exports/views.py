from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from datetime import date

from quizzes.models import QuizAttempt
from .services import QuizResultPDFService, CertificatePDFService


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
    Доступно только для staff пользователей.

    GET /api/exports/preview/certificate/
    GET /api/exports/preview/certificate/?stamp=1
    """

    class MockCertificate:
        holder_name = 'Иванов Иван Иванович'
        course_title = 'Оператор БПЛА. Базовый курс'
        number = 'CERT-2025-001234'
        issued_at = date.today()
        group_name = 'Группа А-101'

    with_stamp = request.GET.get('stamp') == '1'

    service = CertificatePDFService()
    pdf_bytes = service.generate_from_certificate(
        MockCertificate(),
        with_stamp=with_stamp
    )

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="certificate_preview.pdf"'
    return response