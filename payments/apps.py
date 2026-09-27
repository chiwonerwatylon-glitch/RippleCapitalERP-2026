# payments/apps.py
from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "payments"
    verbose_name = "Premium Payments"

    def ready(self):
        # Wire up signals so that installments and commissions are updated
        try:
            import payments.signals  # noqa: F401
        except ImportError:
            pass
