from celery import shared_task
from django.core.management import call_command


@shared_task
def flush_expired_tokens_task():
    """Очистка истекших JWT токенов из blacklist"""
    call_command('flushexpiredtokens')
    return 'Expired tokens flushed'