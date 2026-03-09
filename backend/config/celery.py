# backend/celery.py

import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('medisync')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks(['tasks'])

# ── Beat Schedule ──────────────────────────────────────────────────────
app.conf.beat_schedule = {
    'daily-patient-pipeline': {
        'task': 'tasks.run_daily_pipeline',
        'schedule': crontab(hour=6, minute=0),   # Every day at 6 AM
    },
}