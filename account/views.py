from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate, get_user_model
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone

from .serializers import (
    CheckEmailSerializer,
    UserRegistrationSerializer,
    SetPasswordSerializer,
    LoginSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    UserSerializer,
    UserUpdateSerializer
)
from .models import EmailVerificationToken, PasswordResetToken

User = get_user_model()


class CheckEmailView(APIView):
    """Шаг 1: Проверка существования email"""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CheckEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        user_exists = User.objects.filter(email=email).exists()

        return Response({
            'exists': user_exists,
            'email': email,
            'message': 'Пользователь найден. Введите пароль.' if user_exists else 'Email свободен. Продолжите регистрацию.'
        })


class RegisterView(APIView):
    """Шаг 2: Регистрация пользователя"""
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email', '').lower().strip()

        if not email:
            return Response(
                {'error': 'Email обязателен'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Проверка существования email
        if User.objects.filter(email=email).exists():
            return Response(
                {'error': 'Пользователь с таким email уже существует'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Добавляем email в данные для сериализатора
        data = request.data.copy()
        data['email'] = email

        serializer = UserRegistrationSerializer(data=data)
        serializer.is_valid(raise_exception=True)

        # Создаем пользователя без пароля
        user = User.objects.create(
            email=email,
            first_name=serializer.validated_data['first_name'],
            last_name=serializer.validated_data['last_name'],
            middle_name=serializer.validated_data.get('middle_name', ''),
            iin=serializer.validated_data['iin'],
            phone=serializer.validated_data.get('phone', ''),
            is_active=False,  # Неактивен до подтверждения email
            is_verified=False
        )

        # Создаем токен для подтверждения email
        token = EmailVerificationToken.objects.create(user=user)

        # Отправляем email с ссылкой
        verification_link = f"{settings.FRONTEND_URL}/set-password?token={token.token}"

        send_mail(
            subject='Подтверждение регистрации',
            message=f'Здравствуйте, {user.first_name}!\n\n'
                    f'Для завершения регистрации и установки пароля перейдите по ссылке:\n'
                    f'{verification_link}\n\n'
                    f'Ссылка действительна 24 часа.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )

        return Response({
            'message': 'Регистрация успешна. Проверьте email для установки пароля.',
            'email': user.email
        }, status=status.HTTP_201_CREATED)


class SetPasswordView(APIView):
    """Шаг 3: Установка пароля по токену"""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token_uuid = serializer.validated_data['token']
        password = serializer.validated_data['password']

        try:
            token = EmailVerificationToken.objects.get(token=token_uuid)
        except EmailVerificationToken.DoesNotExist:
            return Response(
                {'error': 'Неверный токен'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not token.is_valid():
            return Response(
                {'error': 'Токен истек или уже использован'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Устанавливаем пароль и активируем пользователя
        user = token.user
        user.set_password(password)
        user.is_active = True
        user.is_verified = True
        user.save()

        # Помечаем токен как использованный
        token.is_used = True
        token.save()

        return Response({
            'message': 'Пароль успешно установлен. Теперь вы можете войти в систему.',
            'email': user.email
        })


class LoginView(APIView):
    """Вход в систему"""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email'].lower().strip()
        password = serializer.validated_data['password']

        user = authenticate(email=email, password=password)

        if user is None:
            return Response(
                {'error': 'Неверный email или пароль'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not user.is_active:
            return Response(
                {'error': 'Аккаунт не активирован. Проверьте email.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Генерируем JWT токены
        refresh = RefreshToken.for_user(user)

        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': UserSerializer(user).data
        })


class PasswordResetRequestView(APIView):
    """Запрос на сброс пароля"""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email'].lower().strip()

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Не раскрываем информацию о существовании email
            return Response({
                'message': 'Если email существует, на него отправлена ссылка для сброса пароля.'
            })

        # Создаем токен для сброса пароля
        token = PasswordResetToken.objects.create(user=user)

        # Отправляем email со ссылкой
        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token.token}"

        send_mail(
            subject='Сброс пароля',
            message=f'Здравствуйте, {user.first_name}!\n\n'
                    f'Для сброса пароля перейдите по ссылке:\n'
                    f'{reset_link}\n\n'
                    f'Ссылка действительна 1 час.\n\n'
                    f'Если вы не запрашивали сброс пароля, проигнорируйте это письмо.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )

        return Response({
            'message': 'Если email существует, на него отправлена ссылка для сброса пароля.'
        })


class PasswordResetConfirmView(APIView):
    """Подтверждение сброса пароля"""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token_uuid = serializer.validated_data['token']
        password = serializer.validated_data['password']

        try:
            token = PasswordResetToken.objects.get(token=token_uuid)
        except PasswordResetToken.DoesNotExist:
            return Response(
                {'error': 'Неверный токен'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not token.is_valid():
            return Response(
                {'error': 'Токен истек или уже использован'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Устанавливаем новый пароль
        user = token.user
        user.set_password(password)
        user.save()

        # Помечаем токен как использованный
        token.is_used = True
        token.save()

        return Response({
            'message': 'Пароль успешно изменен. Теперь вы можете войти с новым паролем.'
        })


class UserProfileView(APIView):
    """Получение и обновление профиля пользователя"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        serializer = UserUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({
            'message': 'Профиль успешно обновлен',
            'user': UserSerializer(request.user).data
        })