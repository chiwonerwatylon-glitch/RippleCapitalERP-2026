# companies/apps.py
from django.apps import AppConfig


class CompaniesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "companies"
    verbose_name = "Insurance Companies"
