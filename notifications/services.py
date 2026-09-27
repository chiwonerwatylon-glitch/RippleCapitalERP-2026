# notifications/services.py
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings

from .models import NotificationLog, NotificationChannel, NotificationType


def _render_email(template_name: str, context: dict) -> str:
    """
    Render an HTML email body from a template.
    """
    return render_to_string(template_name, context)


def send_premium_due_email(installment, user=None) -> NotificationLog | None:
    """
    Send a premium due reminder email for a single installment.

    installment: PremiumInstallment instance.
    """
    policy = installment.policy
    client = policy.client

    if not client.email:
        # Nothing to send to; you might log this as a warning in future.
        return None

    context = {
        "client": client,
        "installment": installment,
        "policy": policy,
    }
    subject = f"Premium Due Reminder - Policy {policy.policy_number}"
    html_message = _render_email("notifications/email_premium_due.html", context)
    recipient = client.email

    send_mail(
        subject=subject,
        message="",  # we send HTML only
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[recipient],
        html_message=html_message,
    )

    return NotificationLog.objects.create(
        client=client,
        policy=policy,
        channel=NotificationChannel.EMAIL,
        notification_type=NotificationType.PREMIUM_DUE,
        recipient=recipient,
        subject=subject,
        message=html_message,
        sent_by=user,
    )


def send_premium_overdue_email(installment, user=None) -> NotificationLog | None:
    """
    Send a premium overdue notice email for a single installment.
    """
    policy = installment.policy
    client = policy.client

    if not client.email:
        return None

    context = {
        "client": client,
        "installment": installment,
        "policy": policy,
    }
    subject = f"Premium Overdue - Policy {policy.policy_number}"
    html_message = _render_email("notifications/email_overdue.html", context)
    recipient = client.email

    send_mail(
        subject=subject,
        message="",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[recipient],
        html_message=html_message,
    )

    return NotificationLog.objects.create(
        client=client,
        policy=policy,
        channel=NotificationChannel.EMAIL,
        notification_type=NotificationType.PREMIUM_OVERDUE,
        recipient=recipient,
        subject=subject,
        message=html_message,
        sent_by=user,
    )
