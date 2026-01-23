from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task
def create_instructor_dossiers_task():
    """
    Создание досье инструкторов
    Запускается ежедневно в 3:00 через Celery Beat
    """
    from django.core.management import call_command

    logger.info("Запуск создания досье инструкторов...")

    try:
        call_command('create_instructor_dossiers')
        logger.info("Досье инструкторов успешно созданы")
    except Exception as e:
        logger.error(f"Ошибка создания досье инструкторов: {e}")
        raise