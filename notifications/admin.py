# notifications/admin.py
from django.contrib import admin
from .models import NotificationLog


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = (
        "notification_type",
        "channel",
        "recipient",
        "client",
        "policy",
        "sent_at",
        "sent_by",
    )
    list_filter = ("notification_type", "channel", "sent_at")
    search_fields = ("recipient", "client__full_name", "policy__policy_number")
    readonly_fields = (
        "client",
        "policy",
        "channel",
        "notification_type",
        "recipient",
        "subject",
        "message",
        "sent_at",
        "sent_by",
    )
