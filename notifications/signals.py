from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
import logging

from .models import NotificationPreference

logger = logging.getLogger(__name__)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_notification_preferences(sender, instance, created, **kwargs):
    """
    Автоматически создать настройки уведомлений для нового пользователя
    """
    if created:
        NotificationPreference.objects.create(user=instance)
        logger.info(f"Созданы настройки уведомлений для {instance.email}")