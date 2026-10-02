from datetime import date, timedelta
from flask import current_app
from .models import db, Policy, NotificationLog


def send_email(to_email: str, subject: str, body: str):
    """
    Simplified email sending stub.
    Replace with real SMTP or provider.
    """
    print(f"Sending email to {to_email}")
    print(f"Subject: {subject}")
    print(body)
    print("----")


def send_expiry_reminders():
    """
    Find policies expiring soon and send reminders.
    Example: 30 days and 7 days before expiry.
    """
    with current_app.app_context():
        today = date.today()
        for days_before in (30, 7, 1):
            target_date = today + timedelta(days=days_before)
            policies = Policy.query.filter(
                Policy.end_date == target_date,
                Policy.status == "active"
            ).all()

            for policy in policies:
                client = policy.client
                if not client.email:
                    continue

                subject = f"Policy {policy.policy_number} Expiry Reminder"
                body = (
                    f"Dear {client.full_name},\n\n"
                    f"Your policy {policy.policy_number} ({policy.product_name}) with "
                    f"{policy.company.name} will expire on {policy.end_date}.\n"
                    f"Days remaining: {days_before}.\n\n"
                    "Please contact your agent if you wish to renew.\n\n"
                    "Best regards,\nInsurance Management System"
                )

                send_email(client.email, subject, body)

                log = NotificationLog(
                    policy_id=policy.id,
                    recipient_email=client.email,
                    notification_type=f"expiry_reminder_{days_before}_days",
                    message=body,
                )
                db.session.add(log)

        db.session.commit()
