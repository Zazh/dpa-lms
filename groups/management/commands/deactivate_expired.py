from django.core.management.base import BaseCommand
from groups.models import Group


class Command(BaseCommand):
    help = 'Деактивировать студентов с истекшим дедлайном'

    def handle(self, *args, **options):
        count = Group.deactivate_expired_memberships()
        self.stdout.write(
            self.style.SUCCESS(f'✅ Деактивировано студентов: {count}')
        )