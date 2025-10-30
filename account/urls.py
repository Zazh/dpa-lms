from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    CheckEmailView,
    RegisterView,
    SetPasswordView,
    LoginView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    UserProfileView
)

app_name = 'account'

urlpatterns = [
    # Регистрация и авторизация
    path('check-email/', CheckEmailView.as_view(), name='check-email'),
    path('register/', RegisterView.as_view(), name='register'),
    path('set-password/', SetPasswordView.as_view(), name='set-password'),
    path('login/', LoginView.as_view(), name='login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),

    # Сброс пароля
    path('password-reset/', PasswordResetRequestView.as_view(), name='password-reset'),
    path('password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),

    # Профиль пользователя
    path('profile/', UserProfileView.as_view(), name='profile'),
]