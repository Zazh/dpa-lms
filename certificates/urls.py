from django.urls import path
from .api_views import CertificateVerifyView

app_name = 'certificates'

urlpatterns = [
    path('verify/<str:number>/', CertificateVerifyView.as_view(), name='verify'),
]