from django.urls import path
from .api_views import (
    NotificationListView,
    NotificationCountView,
    NotificationDetailView,
    NotificationClearAllView,
    NotificationPreferenceView,
)

app_name = 'notifications'

urlpatterns = [
    # Уведомления
    path('', NotificationListView.as_view(), name='notification-list'),
    path('count/', NotificationCountView.as_view(), name='notification-count'),
    path('<int:pk>/', NotificationDetailView.as_view(), name='notification-detail'),
    path('clear/', NotificationClearAllView.as_view(), name='notification-clear'),

    # Настройки
    path('preferences/', NotificationPreferenceView.as_view(), name='notification-preferences'),
]