"""
Сервисы для работы с платежами.

KaspiService — заглушка для Kaspi QR API.
В production заменить на реальную интеграцию.
"""

import uuid
import base64
import json
from django.conf import settings
from django.utils import timezone


class KaspiService:
    """
    Сервис для работы с Kaspi QR API.
    
    ВАЖНО: Это ЗАГЛУШКА для разработки.
    В production нужно реализовать реальную интеграцию с Kaspi.
    """

    # Режим работы: 'stub' или 'production'
    MODE = getattr(settings, 'KASPI_MODE', 'stub')

    # Production настройки (заполнить при подключении)
    API_URL = getattr(settings, 'KASPI_API_URL', '')
    MERCHANT_ID = getattr(settings, 'KASPI_MERCHANT_ID', '')
    API_KEY = getattr(settings, 'KASPI_API_KEY', '')

    @classmethod
    def create_payment(cls, order):
        """
        Создать платёж в Kaspi.
        
        Args:
            order: Order instance
            
        Returns:
            dict: {
                'success': bool,
                'payment_id': str,
                'qr_token': str,
                'qr_payload': str,  # Base64 QR или ссылка
                'error': str (если success=False)
            }
        """
        if cls.MODE == 'stub':
            return cls._create_stub_payment(order)
        else:
            return cls._create_real_payment(order)

    @classmethod
    def check_payment_status(cls, payment_id):
        """
        Проверить статус платежа в Kaspi.
        
        Args:
            payment_id: ID платежа
            
        Returns:
            dict: {
                'status': 'pending' | 'paid' | 'expired' | 'cancelled',
                'paid_at': datetime (если оплачен),
                'error': str (если ошибка)
            }
        """
        if cls.MODE == 'stub':
            return cls._check_stub_payment(payment_id)
        else:
            return cls._check_real_payment(payment_id)

    # ========== STUB IMPLEMENTATION ==========

    # Хранилище для stub платежей (в памяти)
    _stub_payments = {}

    @classmethod
    def _create_stub_payment(cls, order):
        """Создать тестовый платёж (заглушка)"""
        payment_id = f"STUB_{uuid.uuid4().hex[:12].upper()}"

        # Генерируем "QR-код" — просто placeholder
        qr_data = {
            'type': 'kaspi_qr_stub',
            'payment_id': payment_id,
            'amount': str(order.amount),
            'course': order.course.title,
            'merchant': 'Test Merchant',
        }

        # Сохраняем в stub storage
        cls._stub_payments[payment_id] = {
            'order_id': order.id,
            'status': 'pending',
            'created_at': timezone.now(),
        }

        return {
            'success': True,
            'payment_id': payment_id,
            'qr_token': payment_id,
            'qr_payload': json.dumps(qr_data),
        }

    @classmethod
    def _check_stub_payment(cls, payment_id):
        """Проверить статус тестового платежа"""
        if payment_id not in cls._stub_payments:
            return {
                'status': 'error',
                'error': 'Payment not found'
            }

        payment = cls._stub_payments[payment_id]
        return {
            'status': payment['status'],
            'paid_at': payment.get('paid_at'),
        }

    @classmethod
    def simulate_payment(cls, payment_id):
        """
        Симулировать успешную оплату (для тестирования).
        Вызывается вручную или через тестовый endpoint.
        """
        if payment_id in cls._stub_payments:
            cls._stub_payments[payment_id]['status'] = 'paid'
            cls._stub_payments[payment_id]['paid_at'] = timezone.now()
            return True
        return False

    # ========== REAL IMPLEMENTATION (TODO) ==========

    @classmethod
    def _create_real_payment(cls, order):
        """
        Создать реальный платёж в Kaspi QR API.
        
        TODO: Реализовать при подключении Kaspi Business
        
        Документация: https://kaspipay.kz/documents/p5r.pdf
        
        Шаги:
        1. POST /api/v1/qr/create — создать QR
        2. Получить qr_code (base64) и payment_id
        3. Вернуть данные для отображения
        """
        # Placeholder — вернуть ошибку
        return {
            'success': False,
            'error': 'Kaspi integration not configured. Set KASPI_MODE=production and provide API keys.'
        }

    @classmethod
    def _check_real_payment(cls, payment_id):
        """
        Проверить статус реального платежа.
        
        TODO: Реализовать при подключении Kaspi Business
        
        Шаги:
        1. GET /api/v1/qr/status/{payment_id}
        2. Парсить статус: PENDING, PAID, EXPIRED, CANCELLED
        """
        return {
            'status': 'error',
            'error': 'Kaspi integration not configured'
        }


class PaymentEmailService:
    """Сервис email-уведомлений для платежей"""

    @classmethod
    def send_payment_success(cls, order):
        """
        Отправить уведомление об успешной оплате.
        Вызывается когда заказ переходит в статус 'paid'.
        """
        from notifications.services import EmailService

        context = {
            'order': order,
            'course_name': order.course.title,
            'amount': order.amount,
            'complete_registration_url': cls._get_registration_url(order),
        }

        # Если пользователь ещё не зарегистрирован
        if not order.user:
            EmailService.send_template_email(
                to_email=order.email,
                subject=f'Оплата получена — {order.course.title}',
                template='payments/emails/payment_success_unregistered.html',
                context=context
            )
        else:
            # Пользователь уже есть — отправляем подтверждение
            EmailService.send_template_email(
                to_email=order.email,
                subject=f'Вы зачислены на курс — {order.course.title}',
                template='payments/emails/enrollment_success.html',
                context=context
            )

    @classmethod
    def send_complete_registration_reminder(cls, order):
        """
        Напомнить завершить регистрацию.
        Вызывается если оплата есть, но регистрация не завершена.
        """
        from notifications.services import EmailService

        context = {
            'order': order,
            'course_name': order.course.title,
            'complete_registration_url': cls._get_registration_url(order),
        }

        EmailService.send_template_email(
            to_email=order.email,
            subject=f'Завершите регистрацию — {order.course.title}',
            template='payments/emails/complete_registration_reminder.html',
            context=context
        )

    @classmethod
    def _get_registration_url(cls, order):
        """Получить URL для завершения регистрации"""
        frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
        return f"{frontend_url}/?order_token={order.token}"
