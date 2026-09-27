# accounts/apps.py
from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
    verbose_name = "User Accounts & Roles"

    def ready(self):
        """
        Hook for signals.
        """
        try:
            import accounts.signals  # noqa: F401
        except ImportError:
            # Safe during early scaffolding; once signals exist, you can
            # remove this try/except to surface real import errors.
            pass
