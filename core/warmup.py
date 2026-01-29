def warmup():
    """Прогрев Django при старте Gunicorn"""
    from django.contrib.auth import get_user_model
    from django.db import connections

    # Прогреваем подключение к БД
    for conn in connections.all():
        conn.ensure_connection()

    # Прогреваем ORM (загружаем модели)
    User = get_user_model()
    User.objects.first()