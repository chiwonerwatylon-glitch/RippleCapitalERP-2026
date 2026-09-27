"""
commissions/apps.py

App configuration for the Commissions module.
"""

from django.apps import AppConfig


class CommissionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "commissions"
    verbose_name = "Commissions & Revenue"

    def ready(self):
        """
        Called once Django has finished loading all apps.

        This is where we import signal handlers (if/when needed) to
        avoid circular imports and multiple registration during
        development's auto-reload.
        """
        try:
            import commissions.signals  # noqa: F401
        except ImportError:
            # signals.py may not exist during early scaffolding;
            # once it's added, remove this try/except so errors surface.
            pass
