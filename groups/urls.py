from django.urls import path
from .views import JoinGroupByTokenView, GroupInfoView

app_name = 'groups'

urlpatterns = [
    # Информация о группе (БЕЗ авторизации)
    path('info/<uuid:token>/', GroupInfoView.as_view(), name='group-info'),

    # Присоединиться к группе (С авторизацией)
    path('join/<uuid:token>/', JoinGroupByTokenView.as_view(), name='join-by-token'),
]