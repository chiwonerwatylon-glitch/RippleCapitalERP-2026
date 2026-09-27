# notifications/models.py
from django.db import models
from django.conf import settings


class NotificationChannel(models.TextChoices):
    EMAIL = "EMAIL", "Email"
    SMS = "SMS", "SMS"


class NotificationType(models.TextChoices):
    PREMIUM_DUE = "PREMIUM_DUE", "Premium Due Reminder"
    PREMIUM_OVERDUE = "PREMIUM_OVERDUE", "Premium Overdue Reminder"


class NotificationLog(models.Model):
    """
    Audit log of notifications sent to clients.

    This does NOT represent money or policy changes, just the fact that
    Ripple Capital has communicated with a client about their premiums.
    """

    client = models.ForeignKey(
        "clients.Client",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )
    policy = models.ForeignKey(
        "policies.Policy",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )
    channel = models.CharField(
        max_length=10,
        choices=NotificationChannel.choices,
    )
    notification_type = models.CharField(
        max_length=20,
        choices=NotificationType.choices,
    )
    recipient = models.CharField(
        max_length=255,
        help_text="Email address or phone number the notification was sent to.",
    )
    subject = models.CharField(max_length=255, blank=True)
    message = models.TextField(blank=True)

    sent_at = models.DateTimeField(auto_now_add=True)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications_sent",
        help_text="Staff user that triggered the notification, if any.",
    )

    class Meta:
        ordering = ["-sent_at"]
        verbose_name = "Notification Log"
        verbose_name_plural = "Notification Logs"
        indexes = [
            models.Index(fields=["notification_type"]),
            models.Index(fields=["channel"]),
            models.Index(fields=["recipient"]),
            models.Index(fields=["sent_at"]),
        ]

    def __str__(self):
        return f"{self.get_notification_type_display()} to {self.recipient} at {self.sent_at:%Y-%m-%d %H:%M}"
