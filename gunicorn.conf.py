# Gunicorn configuration for 8GB RAM VPS (4 shared CPU)

# Количество воркеров: оптимально для shared CPU + Celery/Redis/PostgreSQL
workers = 6

# 2 потока на воркер для лучшей обработки I/O
threads = 2

# Адрес и порт
bind = "0.0.0.0:8007"

# Тип воркера - gthread для поддержки threads
worker_class = "gthread"

# Таймауты
timeout = 120  # Увеличено для PDF генерации через WeasyPrint
graceful_timeout = 30
keepalive = 5

# Защита от memory leaks
max_requests = 1000
max_requests_jitter = 100

# Логирование
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Перезагрузка при изменении кода (только для dev)
reload = False

# Имя процесса для мониторинга
proc_name = "lms-gunicorn"

# Предзагрузка приложения (экономия памяти)
preload_app = True