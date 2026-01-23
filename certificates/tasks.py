from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def generate_certificate_pdf(self, certificate_id: int):
    """
    Генерация PDF сертификата в фоне

    Args:
        certificate_id: ID сертификата
    """
    from .models import Certificate
    from .services import CertificateService

    try:
        certificate = Certificate.objects.get(id=certificate_id)

        logger.info(f"Генерация сертификата {certificate.number}")

        success = CertificateService.generate_pdf(certificate)

        if success:
            logger.info(f"Сертификат {certificate.number} успешно сгенерирован")
        else:
            logger.error(f"Ошибка генерации сертификата {certificate.number}")

    except Certificate.DoesNotExist:
        logger.error(f"Сертификат {certificate_id} не найден")
    except Exception as e:
        logger.error(f"Ошибка генерации сертификата {certificate_id}: {e}")
        # Повторная попытка через 60 секунд
        raise self.retry(exc=e, countdown=60)


@shared_task
def generate_certificates_bulk(certificate_ids: list):
    """
    Массовая генерация сертификатов

    Args:
        certificate_ids: список ID сертификатов
    """
    logger.info(f"Запуск массовой генерации {len(certificate_ids)} сертификатов")

    for cert_id in certificate_ids:
        generate_certificate_pdf.delay(cert_id)

    logger.info(f"Все задачи генерации поставлены в очередь")