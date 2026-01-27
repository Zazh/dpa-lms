import logging
import uuid


from django.contrib.auth import authenticate, get_user_model
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from notifications.services import EmailService
from .models import EmailVerificationToken, PasswordResetToken, EgovAuthSession
from .serializers import (
    CheckEmailSerializer,
    UserRegistrationSerializer,
    SetPasswordSerializer,
    LoginSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    UserSerializer,
    UserUpdateSerializer,
    EgovInitSerializer,
    EgovCheckStatusSerializer,
    EgovStatusResponseSerializer,
    EgovRegistrationSerializer,
)
from .services import SigexAuthService

logger = logging.getLogger(__name__)

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

        # Получаем referral_token если есть
        referral_token = serializer.validated_data.pop('referral_token', None)  # ← ДОБАВИТЬ

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

        # Сохраняем referral_token в токене для использования после установки пароля
        if referral_token:  # ← ДОБАВИТЬ
            # Сохраняем в completion_data (временно, можно использовать это поле)
            # Или создайте отдельное поле в EmailVerificationToken
            # Для простоты сохраним в сессии через frontend
            pass

        # Отправляем email с ссылкой
        EmailService.send_verification_email(user=user, token=token.token)

        return Response({
            'message': 'Регистрация успешна. Проверьте email для установки пароля.',
            'email': user.email,
            'referral_token': str(referral_token) if referral_token else None  # ← ДОБАВИТЬ (отправляем обратно)
        }, status=status.HTTP_201_CREATED)


class SetPasswordView(APIView):
    """Шаг 3: Установка пароля по токену"""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token_uuid = serializer.validated_data['token']
        password = serializer.validated_data['password']
        referral_token = request.data.get('referral_token')

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

        # ← ДОБАВИТЬ: Отправляем уведомление о завершении регистрации
        from notifications.services import NotificationService
        NotificationService.notify_registration_completed(user)

        # АВТОМАТИЧЕСКОЕ ЗАЧИСЛЕНИЕ ПО РЕФЕРАЛЬНОЙ ССЫЛКЕ
        enrollment_info = None
        if referral_token:
            try:
                from groups.models import Group
                from progress.models import CourseEnrollment, LessonProgress
                from content.models import Lesson

                group = Group.objects.get(referral_token=referral_token, is_active=True)

                # Проверяем, что группа не заполнена
                if not group.is_full():
                    # Добавляем в группу
                    success, message = group.add_student(user, enrolled_via_referral=True)

                    if success:
                        # Создаем зачисление
                        enrollment = CourseEnrollment.objects.create(
                            user=user,
                            course=group.course,
                            group=group,
                            is_active=True
                        )

                        # Инициализируем прогресс
                        lessons = Lesson.objects.filter(module__course=group.course).order_by('module__order', 'order')
                        for lesson in lessons:
                            progress = LessonProgress.objects.create(
                                user=user,
                                lesson=lesson,
                                is_completed=False
                            )
                            progress.calculate_available_at()

                        enrollment_info = {
                            'course': group.course.title,
                            'group': group.name,
                        }
            except Group.DoesNotExist:
                pass  # Токен невалидный - игнорируем

        response_data = {
            'message': 'Пароль успешно установлен. Теперь вы можете войти в систему.',
            'email': user.email
        }

        if enrollment_info:
            response_data['enrollment'] = enrollment_info
            response_data['message'] = f'Пароль установлен! Вы зачислены на курс "{enrollment_info["course"]}"'

        return Response(response_data)


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
        EmailService.send_password_reset_email(user=user, token=token.token)

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


@extend_schema(
    tags=['eGov Auth'],
    summary='Инициализация eGov авторизации',
    description='Создаёт сессию для авторизации через eGov Mobile QR',
    responses={200: EgovInitSerializer}
)
class EgovInitView(APIView):
    """Инициализация QR-подписания через eGov Mobile"""
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Инициализация eGov авторизации",
        description="Создает новую сессию для авторизации через eGov Mobile QR",
        responses={200: EgovInitSerializer}
    )
    def post(self, request):
        try:
            # Генерируем уникальный временный qr_id
            temp_qr_id = f"temp_{uuid.uuid4().hex}"

            # Создаём сессию с уникальным временным значением
            session = EgovAuthSession.objects.create(
                qr_id=temp_qr_id,
                status='pending'
            )

            # Вызываем сервис с ID сессии
            result = SigexAuthService.init_qr_signing(session.id)

            # Обновляем qr_id на реальный от Sigex
            session.qr_id = result['qr_id']
            session.save()

            response_data = {
                'session_id': str(session.id),
                'qr_code': result['qr_code'],
                'egov_mobile_link': result['egov_mobile_link'],
                'egov_business_link': result['egov_business_link'],
                'expires_in': 300
            }

            serializer = EgovInitSerializer(response_data)
            return Response(serializer.data)

        except Exception as e:
            logger.error(f'EgovInitView error: {e}')
            # Удаляем сессию если была создана но произошла ошибка
            if 'session' in locals():
                session.delete()
            return Response(
                {'error': 'Ошибка инициализации eGov авторизации'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

@extend_schema(
    tags=['eGov Auth'],
    summary='Проверка статуса eGov авторизации',
    description='Проверяет, подписал ли пользователь запрос в eGov Mobile',
    request=EgovCheckStatusSerializer,
    responses={200: EgovStatusResponseSerializer}
)
class EgovCheckStatusView(APIView):
    """Проверка статуса авторизации через eGov"""
    permission_classes = [AllowAny]

    def post(self, request):
        session_id = request.data.get('session_id')

        if not session_id:
            return Response(
                {'error': 'session_id обязателен'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            session = EgovAuthSession.objects.get(id=session_id)
        except EgovAuthSession.DoesNotExist:
            return Response(
                {'error': 'Сессия не найдена'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Проверяем статус из БД (обновляется фоновым потоком)
        if session.status == 'signed':
            # Ищем пользователя по ИИН
            user = None
            if session.iin:
                from account.models import User
                user = User.objects.filter(iin=session.iin).first()

            if user:
                from rest_framework_simplejwt.tokens import RefreshToken
                refresh = RefreshToken.for_user(user)

                session.user = user
                session.status = 'completed'
                session.save()

                return Response({
                    'status': 'completed',
                    'user_exists': True,
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                })
            else:
                return Response({
                    'status': 'signed',
                    'user_exists': False,
                    'registration_token': str(session.id),
                    'registration_data': {
                        'iin': session.iin,
                        'first_name': session.first_name,
                        'last_name': session.last_name,
                        'middle_name': session.middle_name,
                    }
                })

        elif session.status == 'error':
            return Response({
                'status': 'error',
                'error': 'Ошибка подписания'
            })

        elif session.status == 'expired':
            return Response({
                'status': 'expired',
                'error': 'Сессия истекла'
            })

        else:
            return Response({
                'status': 'pending'
            })

@extend_schema(
    tags=['eGov Auth'],
    summary='Завершение регистрации после eGov',
    description='Создаёт пользователя с данными из eGov и отправляет email для подтверждения',
    request=EgovRegistrationSerializer,
)
class EgovCompleteRegistrationView(APIView):
    """Завершение регистрации после eGov авторизации"""
    permission_classes = [AllowAny]

    def post(self, request):
        registration_token = request.data.get('registration_token')
        email = request.data.get('email', '').lower().strip()
        phone = request.data.get('phone')

        if not registration_token:
            return Response(
                {'error': 'registration_token обязателен'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not email:
            return Response(
                {'error': 'Email обязателен'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Ищем сессию
        try:
            session = EgovAuthSession.objects.get(id=registration_token, status='signed')
        except (EgovAuthSession.DoesNotExist, ValueError):
            return Response(
                {'error': 'Сессия не найдена или уже использована'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Проверяем истечение
        if session.is_expired():
            session.status = 'expired'
            session.save()
            return Response(
                {'error': 'Сессия истекла'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Проверяем email
        if User.objects.filter(email=email).exists():
            return Response(
                {'error': 'Пользователь с таким email уже существует'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Проверяем ИИН (на случай если кто-то успел зарегистрироваться)
        if User.objects.filter(iin=session.iin).exists():
            return Response(
                {'error': 'Пользователь с таким ИИН уже зарегистрирован'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Обрабатываем телефон
        clean_phone = None
        if phone:
            phone = phone.strip()
            if phone and phone != '+7':
                import re
                clean_phone = re.sub(r'[^\d+]', '', phone)
                if clean_phone and User.objects.filter(phone=clean_phone).exists():
                    return Response(
                        {'error': 'Пользователь с таким телефоном уже зарегистрирован'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

        # Создаём пользователя БЕЗ пароля, неактивного
        user = User.objects.create(
            email=email,
            iin=session.iin,
            first_name=session.first_name or '',
            last_name=session.last_name or '',
            middle_name=session.middle_name or '',
            phone=clean_phone,
            is_active=False,
            is_verified=False
        )

        # Создаём токен для подтверждения email и установки пароля
        token = EmailVerificationToken.objects.create(user=user)

        # Отправляем email
        EmailService.send_verification_email(user=user, token=token.token)

        # Обновляем сессию
        session.status = 'completed'
        session.user = user
        session.save()

        return Response({
            'message': 'Регистрация почти завершена. Проверьте email для установки пароля.',
            'email': user.email
        }, status=status.HTTP_201_CREATED)