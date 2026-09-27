# policies/apps.py
from django.apps import AppConfig


class PoliciesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "policies"
    verbose_name = "Policies & Installments"

    def ready(self):
        try:
            import policies.signals  # noqa: F401
        except ImportError:
            pass
