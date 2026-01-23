from django.utils import timezone
from django.core.files.base import ContentFile

from .models import Certificate


class CertificateService:
    """Сервис для работы с сертификатами"""

    @classmethod
    def create_from_graduate(cls, graduate) -> Certificate:
        """
        Создать сертификат из Graduate

        Args:
            graduate: Graduate instance

        Returns:
            Certificate instance (status=pending)
        """
        certificate = Certificate.objects.create(
            source='internal',
            status='pending',
            user=graduate.user,
            graduate=graduate,
            number=Certificate.generate_number(),
            holder_name=graduate.user.get_full_name(),
            course_title=graduate.course.title,
            group_name=graduate.group.name if graduate.group else '',
            issued_at=timezone.localdate(),
        )

        return certificate

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
    def create_and_generate(cls, graduate) -> Certificate:
        """
        Создать сертификат и сразу сгенерировать PDF (синхронно)

        Args:
            graduate: Graduate instance

        Returns:
            Certificate instance
        """
        certificate = cls.create_from_graduate(graduate)
        cls.generate_pdf(certificate)
        return certificate