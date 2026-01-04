from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('admin/', admin.site.urls),

    # API документация
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),

    # API endpoints
    path('api/account/', include('account.urls')),
    # path('api/courses/', include('courses.urls')),
    path('api/groups/', include('groups.urls')),
    path('api/', include('content.urls')),
    path('api/', include('progress.urls')),
    path('api/quizzes/', include('quizzes.urls')),
    path('api/assignments/', include('assignments.urls')),
    path('api/notifications/', include('notifications.urls')),
    path('api/graduates/', include('graduates.urls')),

    path('backoffice/', include('backoffice.urls')),

    # Kaspi
    path('api/', include('payments.urls')),

]

# Для разработки - отдача медиа и статических файлов
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)