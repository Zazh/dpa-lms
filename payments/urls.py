from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # ============================================================
    # API ENDPOINTS (для Vue.js)
    # ============================================================

    # Создание заказа
    path(
        'payments/orders/create/',
        views.create_order_api,
        name='create_order'
    ),

    # Статус заказа (для polling)
    path(
        'payments/orders/<str:token>/status/',
        views.order_status_api,
        name='order_status'
    ),

    # Информация о заказе (для предзаполнения форм)
    path(
        'payments/orders/<str:token>/info/',
        views.order_info_api,
        name='order_info'
    ),

    # Данные для страницы оплаты
    path(
        'payments/orders/<str:token>/payment-data/',
        views.payment_page_data_api,
        name='payment_data'
    ),

    # Завершение заказа (после авторизации)
    path(
        'payments/orders/<str:token>/complete/',
        views.complete_order_api,
        name='complete_order'
    ),

    # Информация о курсе для покупки
    path(
        'payments/courses/<int:course_id>/purchase-info/',
        views.course_purchase_info_api,
        name='course_purchase_info'
    ),

    # ============================================================
    # STUB ENDPOINT (только для разработки)
    # ============================================================

    path(
        'payments/orders/<str:token>/simulate-payment/',
        views.simulate_payment_api,
        name='simulate_payment'
    ),
]