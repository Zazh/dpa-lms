"""
Views для системы оплаты.

Включает:
- Страницы checkout (для лендинга, если нужен серверный рендеринг)
- API endpoints для Vue.js SPA
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.conf import settings

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from content.models import Course
from groups.models import Group, GroupMembership
from .models import CoursePrice, Order
from .services import KaspiService, PaymentEmailService


# ============================================================
# API ENDPOINTS (для Vue.js)
# ============================================================

@api_view(['POST'])
@permission_classes([AllowAny])
def create_order_api(request):
    """
    Создать заказ на покупку курса.
    
    POST /api/payments/orders/create/
    
    Body:
        {
            "course_slug": "drone-pilot",
            "email": "user@example.com",
            "phone": "+77001234567"
        }
    
    Returns:
        {
            "success": true,
            "order_token": "abc123...",
            "redirect_url": "/checkout/pay/abc123.../"
        }
    """
    course_slug = request.data.get('course_slug')
    email = request.data.get('email', '').strip().lower()
    phone = request.data.get('phone', '').strip()

    # Валидация
    if not course_slug:
        return Response(
            {'error': 'Не указан курс'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if not email:
        return Response(
            {'error': 'Email обязателен'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Получаем курс
    try:
        course = Course.objects.get(id=course_slug, is_active=True)
    except Course.DoesNotExist:
        try:
            # Пробуем по slug если это не ID
            course = Course.objects.get(title__iexact=course_slug, is_active=True)
        except Course.DoesNotExist:
            return Response(
                {'error': 'Курс не найден'},
                status=status.HTTP_404_NOT_FOUND
            )

    # Получаем цену
    try:
        price_settings = CoursePrice.objects.get(course=course, is_active=True)
    except CoursePrice.DoesNotExist:
        return Response(
            {'error': 'Онлайн-покупка этого курса недоступна'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Получаем дефолтную группу
    try:
        default_group = Group.objects.get(course=course, is_default=True, is_active=True)
    except Group.DoesNotExist:
        return Response(
            {'error': 'Группа для записи не настроена'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    # Проверяем, не записан ли уже
    if Order.check_existing_enrollment(email, course, default_group):
        return Response(
            {'error': 'Вы уже записаны на этот курс'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Создаём заказ
    order = Order.objects.create(
        email=email,
        phone=phone,
        course=course,
        group=default_group,
        amount=price_settings.price,
    )

    # Создаём платёж в Kaspi
    kaspi_result = KaspiService.create_payment(order)

    if not kaspi_result['success']:
        order.status = 'cancelled'
        order.save()
        return Response(
            {'error': kaspi_result.get('error', 'Ошибка создания платежа')},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    # Сохраняем данные Kaspi
    order.kaspi_payment_id = kaspi_result['payment_id']
    order.kaspi_qr_token = kaspi_result['qr_token']
    order.kaspi_qr_payload = kaspi_result['qr_payload']
    order.save()

    return Response({
        'success': True,
        'order_token': order.token,
        'redirect_url': f'/checkout/pay/{order.token}/',
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def order_status_api(request, token):
    """
    Получить статус заказа (для polling).
    
    GET /api/payments/orders/{token}/status/
    
    Returns:
        {
            "status": "pending" | "paid" | "expired" | "completed",
            "time_remaining": 1800,  // секунды до истечения
            "is_expired": false
        }
    """
    try:
        order = Order.objects.get(token=token)
    except Order.DoesNotExist:
        return Response(
            {'error': 'Заказ не найден'},
            status=status.HTTP_404_NOT_FOUND
        )

    # Если pending — проверяем статус в Kaspi
    if order.status == 'pending' and order.kaspi_payment_id:
        kaspi_status = KaspiService.check_payment_status(order.kaspi_payment_id)

        if kaspi_status.get('status') == 'paid':
            order.mark_as_paid(order.kaspi_payment_id)
            # Отправляем email
            PaymentEmailService.send_payment_success(order)

    # Проверяем истечение
    if order.status == 'pending' and order.is_expired():
        order.mark_as_expired()

    return Response({
        'status': order.status,
        'time_remaining': order.get_time_remaining(),
        'is_expired': order.is_expired(),
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def order_info_api(request, token):
    """
    Получить информацию о заказе.
    Используется для предзаполнения формы регистрации.
    
    GET /api/payments/orders/{token}/info/
    
    Returns:
        {
            "email": "user@example.com",
            "phone": "+77001234567",
            "course_name": "Пилот дронов",
            "amount": "150000.00",
            "status": "paid"
        }
    """
    try:
        order = Order.objects.select_related('course').get(token=token)
    except Order.DoesNotExist:
        return Response(
            {'error': 'Заказ не найден'},
            status=status.HTTP_404_NOT_FOUND
        )

    return Response({
        'email': order.email,
        'phone': order.phone,
        'course_name': order.course.title,
        'amount': str(order.amount),
        'status': order.status,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complete_order_api(request, token):
    """
    Завершить заказ: привязать к пользователю и зачислить на курс.
    Вызывается ПОСЛЕ успешной авторизации.
    
    POST /api/payments/orders/{token}/complete/
    
    Returns:
        {
            "success": true,
            "message": "Вы успешно зачислены на курс",
            "course_name": "Пилот дронов"
        }
    """
    try:
        order = Order.objects.select_related('course', 'group').get(token=token)
    except Order.DoesNotExist:
        return Response(
            {'error': 'Заказ не найден'},
            status=status.HTTP_404_NOT_FOUND
        )

    # Проверяем статус
    if order.status == 'completed':
        return Response({
            'success': True,
            'message': 'Заказ уже завершён',
            'course_name': order.course.title
        })

    if order.status != 'paid':
        return Response(
            {'error': 'Заказ не оплачен'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Завершаем заказ
    success, message = order.complete(request.user)

    if not success:
        return Response(
            {'error': message},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Отправляем email о зачислении
    PaymentEmailService.send_payment_success(order)

    return Response({
        'success': True,
        'message': message,
        'course_name': order.course.title
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def payment_page_data_api(request, token):
    """
    Данные для страницы оплаты.
    
    GET /api/payments/orders/{token}/payment-data/
    
    Returns:
        {
            "order": {...},
            "qr_payload": "...",
            "kaspi_deeplink": "...",
            "time_remaining": 1800
        }
    """
    try:
        order = Order.objects.select_related('course').get(token=token)
    except Order.DoesNotExist:
        return Response(
            {'error': 'Заказ не найден'},
            status=status.HTTP_404_NOT_FOUND
        )

    if order.status != 'pending':
        return Response({
            'error': 'Заказ уже обработан',
            'status': order.status,
            'redirect': order.status == 'paid'
        })

    if order.is_expired():
        order.mark_as_expired()
        return Response({
            'error': 'Срок оплаты истёк',
            'status': 'expired'
        })

    # Формируем deeplink для Kaspi (если есть)
    kaspi_deeplink = None
    if order.kaspi_qr_token:
        # Формат deeplink зависит от реализации Kaspi
        kaspi_deeplink = f"kaspi://pay?token={order.kaspi_qr_token}"

    return Response({
        'order': {
            'token': order.token,
            'email': order.email,
            'course_name': order.course.title,
            'amount': str(order.amount),
            'status': order.status,
        },
        'qr_payload': order.kaspi_qr_payload,
        'kaspi_deeplink': kaspi_deeplink,
        'time_remaining': order.get_time_remaining(),
        'expires_at': order.expires_at.isoformat(),
    })


# ============================================================
# STUB ENDPOINT (только для разработки)
# ============================================================

@api_view(['POST'])
@permission_classes([AllowAny])
def simulate_payment_api(request, token):
    """
    Симулировать успешную оплату (только для разработки).
    """
    if not settings.DEBUG:
        return Response(
            {'error': 'Доступно только в режиме разработки'},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        order = Order.objects.get(token=token)
    except Order.DoesNotExist:
        return Response(
            {'error': 'Заказ не найден'},
            status=status.HTTP_404_NOT_FOUND
        )

    if order.status != 'pending':
        return Response(
            {'error': f'Заказ уже имеет статус: {order.status}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Симулируем оплату в Kaspi
    if order.kaspi_payment_id:
        KaspiService.simulate_payment(order.kaspi_payment_id)

    # Обновляем заказ
    order.mark_as_paid(order.kaspi_payment_id)

    # 🆕 Отправляем email со ссылкой на регистрацию
    PaymentEmailService.send_payment_success(order)

    return Response({
        'success': True,
        'message': 'Оплата симулирована',
        'status': order.status
    })


# ============================================================
# COURSE INFO (для лендинга)
# ============================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def course_purchase_info_api(request, course_id):
    """
    Информация о курсе для покупки.
    
    GET /api/payments/courses/{course_id}/purchase-info/
    
    Returns:
        {
            "course": {
                "id": 1,
                "title": "Пилот дронов",
                "description": "...",
            },
            "price": "150000.00",
            "is_available": true,
            "available_slots": "∞" | 10
        }
    """
    try:
        course = Course.objects.get(id=course_id, is_active=True)
    except Course.DoesNotExist:
        return Response(
            {'error': 'Курс не найден'},
            status=status.HTTP_404_NOT_FOUND
        )

    # Цена
    try:
        price_settings = CoursePrice.objects.get(course=course, is_active=True)
        price = str(price_settings.price)
        is_available = True
    except CoursePrice.DoesNotExist:
        price = None
        is_available = False

    # Дефолтная группа
    try:
        default_group = Group.objects.get(course=course, is_default=True, is_active=True)
        available_slots = default_group.get_available_slots()
    except Group.DoesNotExist:
        available_slots = 0
        is_available = False

    return Response({
        'course': {
            'id': course.id,
            'title': course.title,
            'description': course.description,
            'label': course.label,
            'duration': course.duration,
        },
        'price': price,
        'is_available': is_available,
        'available_slots': available_slots,
    })
