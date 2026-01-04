"""
Management command для проверки pending платежей.

Запускать через cron каждую минуту:
* * * * * cd /path/to/project && python manage.py check_pending_payments

Что делает:
1. Проверяет статус pending заказов в Kaspi API
2. Обновляет статус оплаченных заказов
3. Отправляет email если оплата получена
4. Помечает истёкшие заказы
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from payments.models import Order
from payments.services import KaspiService, PaymentEmailService


class Command(BaseCommand):
    help = 'Проверить pending платежи в Kaspi и обновить статусы'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Только показать что будет сделано, без изменений',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        self.stdout.write(self.style.NOTICE(
            f'[{timezone.now().strftime("%Y-%m-%d %H:%M:%S")}] '
            f'Проверка pending платежей...'
        ))

        # 1. Проверяем pending заказы в Kaspi
        pending_orders = Order.get_pending_orders()
        self.stdout.write(f'  Найдено pending заказов: {pending_orders.count()}')

        paid_count = 0
        for order in pending_orders:
            if not order.kaspi_payment_id:
                continue

            # Проверяем статус в Kaspi
            kaspi_status = KaspiService.check_payment_status(order.kaspi_payment_id)

            if kaspi_status.get('status') == 'paid':
                if dry_run:
                    self.stdout.write(
                        f'  [DRY-RUN] Заказ #{order.id} оплачен'
                    )
                else:
                    order.mark_as_paid(order.kaspi_payment_id)
                    PaymentEmailService.send_payment_success(order)
                    self.stdout.write(self.style.SUCCESS(
                        f'  ✅ Заказ #{order.id} помечен как оплаченный'
                    ))
                paid_count += 1

        # 2. Помечаем истёкшие заказы
        if dry_run:
            expired_count = Order.objects.filter(
                status='pending',
                expires_at__lte=timezone.now()
            ).count()
            self.stdout.write(
                f'  [DRY-RUN] Будет помечено истёкших: {expired_count}'
            )
        else:
            expired_count = Order.expire_old_orders()
            if expired_count > 0:
                self.stdout.write(self.style.WARNING(
                    f'  ⏰ Помечено истёкших заказов: {expired_count}'
                ))

        # 3. Напоминаем о незавершённой регистрации
        # (оплачено более 1 часа назад, но регистрация не завершена)
        one_hour_ago = timezone.now() - timezone.timedelta(hours=1)
        unfinished_orders = Order.objects.filter(
            status='paid',
            user__isnull=True,
            paid_at__lte=one_hour_ago,
            paid_at__gte=one_hour_ago - timezone.timedelta(hours=1)  # Только последний час
        )

        reminder_count = 0
        for order in unfinished_orders:
            if dry_run:
                self.stdout.write(
                    f'  [DRY-RUN] Напоминание для заказа #{order.id}'
                )
            else:
                PaymentEmailService.send_complete_registration_reminder(order)
                self.stdout.write(self.style.NOTICE(
                    f'  📧 Отправлено напоминание для заказа #{order.id}'
                ))
            reminder_count += 1

        # Итог
        self.stdout.write(self.style.SUCCESS(
            f'  Готово: оплачено={paid_count}, истекло={expired_count}, напоминаний={reminder_count}'
        ))
