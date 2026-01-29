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

    # Прогреваем основные модели
    User = get_user_model()
    User.objects.first()

    from content.models import Course
    from progress.models import CourseEnrollment
    from graduates.models import Graduate
    from notifications.models import Notification

    Course.objects.first()
    Notification.objects.first()
    CourseEnrollment.objects.first()
    Graduate.objects.first()

    logger.info("✅ ORM models loaded")

    # Прогреваем URL routing
    from django.urls import resolve
    try:
        resolve('/api/courses/')
        resolve('/api/account/profile/')
        resolve('/api/graduates/me/')
        resolve('/api/notifications/count/')
    except:
        pass
    logger.info("✅ URL routing loaded")

    logger.info("🔥 Warmup completed!")