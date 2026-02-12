import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def deactivate_expired_memberships_task():
    """
    Деактивировать членства с истекшим дедлайном.
    Запускается каждый час через Celery Beat.
    """
    from groups.models import Group

    count = Group.deactivate_expired_memberships()

    if count > 0:
        logger.info(f'Деактивировано членств с истекшим дедлайном: {count}')

    return f'Деактивировано: {count}'
