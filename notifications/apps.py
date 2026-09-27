# notifications/apps.py
from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "notifications"
    verbose_name = "Notifications & Reminders"

    def ready(self):
        """
        Place to wire up signals when needed.
        Right now we don't use signals in this app, but leaving the
        hook here is standard practice.
        """
        try:
            import notifications.signals  # noqa: F401
        except ImportError:
            # Safe during early development; remove the try/except once
            # signals.py is used so errors surface immediately.
            pass
