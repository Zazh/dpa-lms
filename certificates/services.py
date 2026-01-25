from django.utils import timezone
from django.core.files.base import ContentFile

from .models import Certificate, CertificateTemplate


class CertificateService:
    """Сервис для работы с сертификатами"""

    @classmethod
    def _get_holder_name(cls, user) -> str:
        """Получить ФИ (без отчества) для сертификата"""
        parts = []
        if user.last_name:
            parts.append(user.last_name)
        if user.first_name:
            parts.append(user.first_name)
        return ' '.join(parts) or user.email

    @classmethod
    def certificate_exists(cls, user, course, certificate_type: str = 'certificate') -> bool:
        """Проверить существует ли уже сертификат"""
        return Certificate.objects.filter(
            user=user,
            course=course,
            certificate_type=certificate_type
        ).exists()

    @classmethod
    def create_from_graduate(
            cls,
            graduate,
            certificate_type: str = 'certificate'
    ) -> Certificate:
        """
        Создать сертификат из Graduate

        Args:
            graduate: Graduate instance
            certificate_type: 'certificate' или 'attended'

        Returns:
            Certificate instance (status=pending)

        Raises:
            ValueError: если сертификат уже существует
        """
        # Проверка на дубликат
        if cls.certificate_exists(graduate.user, graduate.course, certificate_type):
            raise ValueError(
                f'Сертификат типа "{certificate_type}" для этого пользователя '
                f'и курса уже существует'
            )

        # Получаем шаблон курса
        template = cls._get_template(graduate.course)

        # Определяем тексты в зависимости от типа
        if certificate_type == 'attended':
            document_title = template.attended_title if template else 'СПРАВКА'
            completion_text = template.attended_text if template else 'прослушал(а) курс'
        else:
            document_title = template.certificate_title if template else 'СЕРТИФИКАТ'
            completion_text = template.completion_text if template else 'успешно завершил(а) курс'

        certificate = Certificate.objects.create(
            source='internal',
            status='pending',
            certificate_type=certificate_type,
            user=graduate.user,
            graduate=graduate,
            course=graduate.course,
            number=Certificate.generate_number(),
            holder_name=cls._get_holder_name(graduate.user),
            course_title=template.full_course_title if template else graduate.course.title,
            group_name=graduate.group.name if graduate.group else '',
            issued_at=timezone.localdate(),
            # Данные из шаблона
            document_title=document_title,
            completion_text=completion_text,
            issue_date_label=template.issue_date_label if template else 'Дата выдачи:',
            stamp_css_class=template.stamp_css_class if template else 'stamp-img-1',
            signature_css_class=template.signature_css_class if template else 'aft-img-1',
            signer_name=template.signer_name if template else '',
            signer_position=template.signer_position if template else '',
        )

        return certificate

    @classmethod
    def _get_template(cls, course) -> 'CertificateTemplate | None':
        """Получить шаблон сертификата для курса"""
        try:
            return course.certificate_template
        except CertificateTemplate.DoesNotExist:
            return None

    @classmethod
    def generate_pdf(cls, certificate: Certificate) -> bool:
        """
        Генерирует PDF файлы для сертификата

        Args:
            certificate: Certificate instance

        Returns:
            bool: успех или нет
        """
        from exports.services import CertificatePDFService

        try:
            service = CertificatePDFService()

            # Генерируем PDF без печати
            pdf_content = service.generate_from_certificate(certificate, with_stamp=False)
            filename = f"cert_{certificate.number}.pdf"
            certificate.file_without_stamp.save(filename, ContentFile(pdf_content), save=False)

            # Генерируем PDF с печатью
            pdf_content_stamp = service.generate_from_certificate(certificate, with_stamp=True)
            filename_stamp = f"cert_{certificate.number}_stamp.pdf"
            certificate.file_with_stamp.save(filename_stamp, ContentFile(pdf_content_stamp), save=False)

            certificate.status = 'ready'
            certificate.error_message = ''
            certificate.save()

            return True

        except Exception as e:
            certificate.status = 'error'
            certificate.error_message = str(e)
            certificate.save()
            return False

    @classmethod
    def create_and_generate(cls, graduate, certificate_type: str = 'certificate') -> Certificate:
        """
        Создать сертификат и сразу сгенерировать PDF (синхронно)
        """
        certificate = cls.create_from_graduate(graduate, certificate_type)
        cls.generate_pdf(certificate)
        return certificate