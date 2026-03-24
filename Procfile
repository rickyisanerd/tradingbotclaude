web: gunicorn dashboard.app:create_app() --bind 0.0.0.0:$PORT --workers 2
worker: python -m bot.scheduler
