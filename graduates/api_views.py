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
        ).select_related('course', 'group').order_by('-completed_at')
        
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
            Graduate,
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
    Скачать сертификат
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pk):
        graduate = get_object_or_404(
            Graduate,
            pk=pk,
            user=request.user
        )
        
        # Проверка что выпуск подтвержден
        if graduate.status != 'graduated':
            return Response(
                {'error': 'Сертификат доступен только после подтверждения выпуска'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Проверка что файл существует
        if not graduate.certificate_file:
            return Response(
                {'error': 'Сертификат еще не загружен'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            # Отдаем файл
            response = FileResponse(
                graduate.certificate_file.open('rb'),
                content_type='application/pdf'
            )
            response['Content-Disposition'] = f'attachment; filename="certificate_{graduate.certificate_number}.pdf"'
            return response
        except FileNotFoundError:
            raise Http404('Файл сертификата не найден')
