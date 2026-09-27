# disbursements/apps.py
from django.apps import AppConfig


class DisbursementsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "disbursements"
    verbose_name = "Disbursements to Insurers"
