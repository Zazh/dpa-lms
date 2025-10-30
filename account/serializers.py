import re
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from .models import EmailVerificationToken, PasswordResetToken

User = get_user_model()


class CheckEmailSerializer(serializers.Serializer):
    """Сериализатор для проверки email (Шаг 1)"""
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.lower().strip()


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Сериализатор для регистрации пользователя (Шаг 2)"""
    email = serializers.EmailField(read_only=True)

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'middle_name', 'iin', 'phone']

    def validate_iin(self, value):
        """Валидация ИИН"""
        value = value.strip()

        if not value.isdigit():
            raise serializers.ValidationError("ИИН должен содержать только цифры")

        if len(value) != 12:
            raise serializers.ValidationError("ИИН должен содержать 12 цифр")

        if User.objects.filter(iin=value).exists():
            raise serializers.ValidationError("Пользователь с таким ИИН уже зарегистрирован")

        return value

    def validate_first_name(self, value):
        """Валидация имени - кириллица или латиница"""
        value = value.strip()

        if not value:
            raise serializers.ValidationError("Имя обязательно для заполнения")

        # Проверка на кириллицу или латиницу, пробелы и дефисы
        if not re.match(r'^[а-яёА-ЯЁa-zA-Z\s\-]+$', value):
            raise serializers.ValidationError("Имя должно содержать только буквы")

        return value

    def validate_last_name(self, value):
        """Валидация фамилии - кириллица или латиница"""
        value = value.strip()

        if not value:
            raise serializers.ValidationError("Фамилия обязательна для заполнения")

        if not re.match(r'^[а-яёА-ЯЁa-zA-Z\s\-]+$', value):
            raise serializers.ValidationError("Фамилия должна содержать только буквы")

        return value

    def validate_middle_name(self, value):
        """Валидация отчества - кириллица или латиница (если заполнено)"""
        if value:
            value = value.strip()
            if not re.match(r'^[а-яёА-ЯЁa-zA-Z\s\-]+$', value):
                raise serializers.ValidationError("Отчество должно содержать только буквы")
        return value if value else ''

    def validate_phone(self, value):
        """Валидация телефона"""
        if value:
            value = value.strip()

            # Если телефон пустой или только +7, считаем его пустым
            if value in ['', '+7']:
                return None

            # Убираем все кроме цифр и +
            clean_phone = re.sub(r'[^\d+]', '', value)

            # Проверяем формат: должен начинаться с +7 и иметь 11 цифр
            if clean_phone:
                if not clean_phone.startswith('+7'):
                    raise serializers.ValidationError("Телефон должен начинаться с +7")

                digits_only = clean_phone.replace('+', '')
                if len(digits_only) != 11:
                    raise serializers.ValidationError("Телефон должен содержать 11 цифр")

                # Проверка на уникальность телефона
                if User.objects.filter(phone=clean_phone).exists():
                    raise serializers.ValidationError("Пользователь с таким телефоном уже зарегистрирован")

                return clean_phone

        return None


class SetPasswordSerializer(serializers.Serializer):
    """Сериализатор для установки пароля (Шаг 3)"""
    token = serializers.UUIDField()
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    password_confirm = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password_confirm": "Пароли не совпадают"})

        # Валидация сложности пароля
        validate_password(attrs['password'])

        return attrs


class LoginSerializer(serializers.Serializer):
    """Сериализатор для входа"""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})


class PasswordResetRequestSerializer(serializers.Serializer):
    """Сериализатор для запроса сброса пароля"""
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Сериализатор для подтверждения сброса пароля"""
    token = serializers.UUIDField()
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    password_confirm = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password_confirm": "Пароли не совпадают"})

        validate_password(attrs['password'])

        return attrs


class UserSerializer(serializers.ModelSerializer):
    """Сериализатор для отображения данных пользователя"""
    full_name = serializers.CharField(source='get_full_name', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'middle_name',
                  'full_name', 'iin', 'phone', 'is_verified', 'date_joined']
        read_only_fields = ['id', 'email', 'is_verified', 'date_joined']


class UserUpdateSerializer(serializers.ModelSerializer):
    """Сериализатор для обновления данных пользователя"""

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'middle_name', 'phone']

    def validate_first_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Имя обязательно для заполнения")
        if not re.match(r'^[а-яёА-ЯЁa-zA-Z\s\-]+$', value):
            raise serializers.ValidationError("Имя должно содержать только буквы")
        return value

    def validate_last_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Фамилия обязательна для заполнения")
        if not re.match(r'^[а-яёА-ЯЁa-zA-Z\s\-]+$', value):
            raise serializers.ValidationError("Фамилия должна содержать только буквы")
        return value

    def validate_phone(self, value):
        """Валидация телефона при обновлении"""
        if value:
            value = value.strip()

            if value in ['', '+7']:
                return None

            clean_phone = re.sub(r'[^\d+]', '', value)

            if clean_phone:
                if not clean_phone.startswith('+7'):
                    raise serializers.ValidationError("Телефон должен начинаться с +7")

                digits_only = clean_phone.replace('+', '')
                if len(digits_only) != 11:
                    raise serializers.ValidationError("Телефон должен содержать 11 цифр")

                # Проверка на уникальность (исключая текущего пользователя)
                if User.objects.filter(phone=clean_phone).exclude(id=self.instance.id).exists():
                    raise serializers.ValidationError("Пользователь с таким телефоном уже зарегистрирован")

                return clean_phone

        return None