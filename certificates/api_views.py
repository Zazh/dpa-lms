from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status

from .models import Certificate


class CertificateVerifyView(APIView):
    """
    GET /api/certificates/verify/{number}/

    Публичная проверка сертификата по номеру
    """
    permission_classes = [AllowAny]

    def get(self, request, number):
        try:
            certificate = Certificate.objects.get(
                number=number.upper(),
                status='ready'
            )

            return Response({
                'valid': True,
                'holder_name': certificate.holder_name,
                'course_title': certificate.course_title,
                'issued_at': certificate.issued_at,
            })

        except Certificate.DoesNotExist:
            return Response({
                'valid': False,
                'message': 'Сертификат не найден'
            }, status=status.HTTP_404_NOT_FOUND)