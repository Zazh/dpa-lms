from django.urls import path
from . import api_views

app_name = 'graduates'

urlpatterns = [
    # Мой статус выпуска
    path('me/', api_views.MyGraduationStatusView.as_view(), name='my-status'),
    
    # Детали выпуска
    path('<int:pk>/', api_views.GraduationDetailView.as_view(), name='detail'),
    
    # Скачать сертификат
    path('<int:pk>/certificate/', api_views.DownloadCertificateView.as_view(), name='download-certificate'),
]
