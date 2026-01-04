from django.core.management.base import BaseCommand
from account.models import User
from dossier.services import DossierService


class Command(BaseCommand):
    help = 'Создать досье для всех инструкторов'

    def handle(self, *args, **options):
        instructors = User.objects.filter(role__in=['instructor', 'super_instructor'])

        count = 0
        for instructor in instructors:
            DossierService.create_or_update_instructor_dossier(instructor)
            count += 1
            self.stdout.write(f'✅ {instructor.email}')

        self.stdout.write(self.style.SUCCESS(f'Создано/обновлено досье: {count}'))