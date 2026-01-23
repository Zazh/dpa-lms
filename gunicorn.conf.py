# Gunicorn configuration
import multiprocessing

# Кол-во воркеров (рекомендуется: 2-4 × CPU cores)
workers = 4

# Адрес и порт
bind = "0.0.0.0:8007"

# Тип воркера
worker_class = "sync"

# Таймауты
timeout = 30
keepalive = 2

# Логирование
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Перезагрузка при изменении кода (только для dev)
reload = False