import logging

logger = logging.getLogger(__name__)


def warmup():
    """Прогрев Django при старте Gunicorn"""
    logger.info("🔥 Warmup started...")

    from django.contrib.auth import get_user_model
    from django.db import connections

    # Прогреваем подключение к БД
    for conn in connections.all():
        conn.ensure_connection()
    logger.info("✅ Database connection established")

    # Прогреваем ORM (загружаем модели)
    User = get_user_model()
    User.objects.first()
    logger.info("✅ ORM models loaded")

    logger.info("🔥 Warmup completed!")