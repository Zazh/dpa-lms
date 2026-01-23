from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.http import FileResponse, Http404
from .models import Graduate
from .serializers import GraduateSerializer, GraduateDetailSerializer


class MyGraduationStatusView(APIView):
    """
    GET /api/graduates/me/
    Мой статус выпуска
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Получаем все выпуски пользователя
        graduates = Graduate.objects.filter(
            user=request.user
        ).select_related('course', 'group', 'certificate').order_by('-completed_at')

        if not graduates.exists():
            return Response({
                'has_graduations': False,
                'message': 'У вас пока нет завершенных курсов'
            })

        serializer = GraduateSerializer(
            graduates,
            many=True,
            context={'request': request}
        )

        return Response({
            'has_graduations': True,
            'graduations': serializer.data
        })


class GraduationDetailView(APIView):
    """
    GET /api/graduates/{id}/
    Детали выпуска
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        graduate = get_object_or_404(
            Graduate.objects.select_related('course', 'group', 'certificate'),
            pk=pk,
            user=request.user
        )

        serializer = GraduateDetailSerializer(
            graduate,
            context={'request': request}
        )

        return Response(serializer.data)


class DownloadCertificateView(APIView):
    """
    GET /api/graduates/{id}/certificate/
    GET /api/graduates/{id}/certificate/?stamp=true
    Скачать сертификат
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        graduate = get_object_or_404(
            Graduate.objects.select_related('certificate'),
            pk=pk,
            user=request.user
        )

        # Проверка что выпуск подтвержден
        if graduate.status != 'graduated':
            return Response(
                {'error': 'Сертификат доступен только после подтверждения выпуска'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Проверка что сертификат существует
        if not hasattr(graduate, 'certificate') or not graduate.certificate:
            return Response(
                {'error': 'Сертификат не найден'},
                status=status.HTTP_404_NOT_FOUND
            )

        certificate = graduate.certificate

        # Проверка что сертификат готов
        if certificate.status != 'ready':
            return Response(
                {'error': 'Сертификат ещё генерируется, попробуйте позже'},
                status=status.HTTP_202_ACCEPTED
            )

        # Выбираем файл: с печатью или без
        with_stamp = request.query_params.get('stamp', '').lower() in ('true', '1', 'yes')

        if with_stamp:
            file_field = certificate.file_with_stamp
            suffix = 'с_печатью'
        else:
            file_field = certificate.file_without_stamp
            suffix = 'без_печати'

        if not file_field:
            return Response(
                {'error': 'Файл сертификата не найден'},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            response = FileResponse(
                file_field.open('rb'),
                content_type='application/pdf'
            )
            response['Content-Disposition'] = f'attachment; filename="certificate_{certificate.number}_{suffix}.pdf"'
            return response
        except FileNotFoundError:
            raise Http404('Файл сертификата не найден')