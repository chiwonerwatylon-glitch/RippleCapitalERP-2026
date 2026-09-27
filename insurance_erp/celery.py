"""
Celery configuration for insurance_erp.

Use this to run background tasks (e.g., premium reminders).
"""

import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "insurance_erp.settings")

app = Celery("insurance_erp")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
