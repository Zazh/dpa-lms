import glob
import os
import uuid
from datetime import date

from django.conf import settings
from django.core.management.base import BaseCommand

from exports.services import CertificatePDFService


# =============================================================================
# РЕДАКТИРУЙТЕ ЭТОТ СПИСОК ПЕРЕД КАЖДЫМ ЗАПУСКОМ
# ИИН: 'Имя Фамилия'
# =============================================================================
HOLDERS = {
    '920401302543': 'Оңласынов Жұлдызбек',
    '030521502077': 'Мирсидиков Шохнур',
    '970412301316': 'Әкім Мирас',
    '020722501426': 'Бейсембаев Самат',
}
# =============================================================================

# Данные сертификата
COURSE_TITLE = 'Первоначальная теоретическая подготовка операторов <br>БАС Категории 2'
COURSE_FOLDER = 'Первоначальная теоретическая подготовка операторов БАС Категории 2'
GROUP_NAME = 'Группа А-101'
DOCUMENT_TITLE = 'СЕРТИФИКАТ'
COMPLETION_TEXT = 'успешно завершил(–а) курс'
ISSUE_DATE_LABEL = 'Дата выдачи:'
STAMP_CSS_CLASS = 'stamp-img-1'
SIGNATURE_CSS_CLASS = 'aft-img-1'
SIGNER_NAME = 'Худайбергенова П.Т.'
SIGNER_POSITION = 'Генеральный директор<br>ТОО "Aerial Solutions"'


def get_existing_numbers(base_dir):
    """Собрать все номера сертификатов из certificates-offline/."""
    numbers = set()
    for pdf_path in glob.glob(os.path.join(base_dir, '**', 'KZ*.pdf'), recursive=True):
        filename = os.path.basename(pdf_path)
        number = filename.replace('_stamp.pdf', '').replace('.pdf', '')
        numbers.add(number)
    return numbers


def generate_number(existing):
    """Генерация уникального номера, не пересекающегося с existing."""
    year = date.today().year
    for _ in range(100):
        unique_id = str(uuid.uuid4())[:6].upper()
        number = f"KZ{year}{unique_id}"
        if number not in existing:
            existing.add(number)
            return number
    raise RuntimeError("Не удалось сгенерировать уникальный номер")


def find_existing_holder(course_dir, iin):
    """Проверить есть ли уже каталог с этим ИИН в каталоге курса."""
    if not os.path.exists(course_dir):
        return False
    suffix = f" {iin}"
    for entry in os.listdir(course_dir):
        if entry.endswith(suffix):
            return entry
    return False


class MockCertificate:
    pass


class Command(BaseCommand):
    help = 'Генерация офлайн-сертификатов в media/certificates-offline/'

    def handle(self, *args, **options):
        service = CertificatePDFService()
        output_base = os.path.join(settings.MEDIA_ROOT, 'certificates-offline')
        course_dir = os.path.join(output_base, COURSE_FOLDER)

        existing_numbers = get_existing_numbers(output_base)

        success_count = 0
        skip_count = 0
        fail_count = 0

        self.stdout.write(f'\nКурс: {COURSE_FOLDER}')
        self.stdout.write(f'Генерация сертификатов для {len(HOLDERS)} человек...\n')

        for iin, name in HOLDERS.items():
            existing = find_existing_holder(course_dir, iin)
            if existing:
                skip_count += 1
                self.stdout.write(self.style.WARNING(
                    f'  ⏭ {name} ({iin}) — уже существует ({existing})'
                ))
                continue

            cert_number = generate_number(existing_numbers)

            mock = MockCertificate()
            mock.holder_name = name
            mock.course_title = COURSE_TITLE
            mock.number = cert_number
            mock.issued_at = date.today()
            mock.group_name = GROUP_NAME
            mock.document_title = DOCUMENT_TITLE
            mock.completion_text = COMPLETION_TEXT
            mock.issue_date_label = ISSUE_DATE_LABEL
            mock.stamp_css_class = STAMP_CSS_CLASS
            mock.signature_css_class = SIGNATURE_CSS_CLASS
            mock.signer_name = SIGNER_NAME
            mock.signer_position = SIGNER_POSITION

            folder_name = f"{name} {iin}"
            cert_dir = os.path.join(course_dir, folder_name)
            os.makedirs(cert_dir, exist_ok=True)

            try:
                pdf_no_stamp = service.generate_from_certificate(mock, with_stamp=False)
                with open(os.path.join(cert_dir, f'{cert_number}.pdf'), 'wb') as f:
                    f.write(pdf_no_stamp)

                pdf_with_stamp = service.generate_from_certificate(mock, with_stamp=True)
                with open(os.path.join(cert_dir, f'{cert_number}_stamp.pdf'), 'wb') as f:
                    f.write(pdf_with_stamp)

                success_count += 1
                self.stdout.write(self.style.SUCCESS(
                    f'  ✓ {name} ({iin}) → {cert_number}'
                ))
            except Exception as e:
                fail_count += 1
                self.stdout.write(self.style.ERROR(
                    f'  ✗ {name} ({iin}) → {e}'
                ))

        self.stdout.write(f'\nГотово: {success_count} новых, {skip_count} пропущено, {fail_count} ошибок')
        self.stdout.write(f'Файлы: {course_dir}/\n')
