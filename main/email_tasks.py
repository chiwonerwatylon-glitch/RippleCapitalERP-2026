"""Transactional email for policy, claim and password-reset notifications.

Railway's Hobby plan blocks outbound SMTP, so mail is sent through Resend's
HTTPS API. Configure with:
  RESEND_API_KEY  - Resend API key (required to actually send)
  MAIL_FROM       - sender address, defaults to noreply@ripplecapitalfinance.co.zw
The sending domain must be verified in Resend.

Every failure is logged and swallowed so that a mail problem never breaks the
request that triggered it.
"""
import json
import logging
import urllib.request
from datetime import date, datetime, timedelta

from flask import current_app
from sqlalchemy import or_

from .models import (
    db,
    Policy,
    User,
    NotificationLog,
    ROLE_OWNER,
    ROLE_ADMIN,
    ROLE_AGENT,
)

RESEND_API_URL = "https://api.resend.com/emails"
STAFF_ROLES = (ROLE_OWNER, ROLE_ADMIN, ROLE_AGENT)
SIGNATURE = "Ripple Capital Insurance\n"

logger = logging.getLogger(__name__)


def send_email(to_email: str, subject: str, body: str) -> bool:
    """Send one plain-text email via Resend. Returns True when accepted."""
    api_key = current_app.config.get("RESEND_API_KEY")
    if not api_key:
        logger.warning("RESEND_API_KEY not set; not sending '%s' to %s", subject, to_email)
        return False

    payload = json.dumps({
        "from": f"Ripple Capital <{current_app.config['MAIL_FROM']}>",
        "to": [to_email],
        "subject": subject,
        "text": body,
    }).encode("utf-8")
    request = urllib.request.Request(
        RESEND_API_URL,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "ripple-capital-erp/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return 200 <= response.status < 300
    except Exception:  # network errors and HTTP errors alike
        logger.exception("Failed to send '%s' to %s", subject, to_email)
        return False


def _unique(emails):
    seen, result = set(), []
    for email in emails:
        if email and email.strip().lower() not in seen:
            seen.add(email.strip().lower())
            result.append(email.strip())
    return result


def staff_emails(owner_id: int):
    """Active owner/admin/agent accounts that work under this owner's account."""
    users = User.query.filter(
        User.is_active.is_(True),
        User.role.in_(STAFF_ROLES),
        or_(User.id == owner_id, User.account_owner_id == owner_id),
    ).all()
    return [u.email for u in users]


def client_emails(client):
    """The client's contact email and the email of their login account, if any."""
    if client is None:
        return []
    emails = [client.email]
    if client.user_id:
        user = User.query.get(client.user_id)
        if user and user.is_active:
            emails.append(user.email)
    return emails


def _log_and_send(recipients, notification_type, subject, body, policy_id=None, claim_id=None):
    for recipient in recipients:
        sent = send_email(recipient, subject, body)
        db.session.add(NotificationLog(
            policy_id=policy_id,
            claim_id=claim_id,
            recipient_email=recipient,
            notification_type=notification_type,
            subject=subject,
            message=body,
            status="sent" if sent else "failed",
        ))
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("Could not write notification log for '%s'", subject)


# ==================== POLICIES ====================

POLICY_EVENT_TEXT = {
    "created": "has been created",
    "payment": "has received a premium payment",
    "deleted": "has been cancelled and removed",
    "expiring": "is due to expire soon",
}


def policy_snapshot(policy: Policy) -> dict:
    """Copy the fields needed for a notification. Call before deleting a policy."""
    client = policy.client
    return {
        "id": policy.id,
        "policy_number": policy.policy_number,
        "client_name": client.full_name() if client else "",
        "product_name": policy.product_name or "",
        "company_name": policy.company.name if policy.company else "",
        "end_date": policy.end_date,
        "outstanding": policy.outstanding_premium(),
        "recipients": _unique(client_emails(client) + staff_emails(policy.owner_id)),
    }


def notify_policy(snapshot: dict, event: str, note: str = "", notification_type: str = None) -> None:
    """Email the client and account staff about a change to a policy."""
    policy_id = None if event == "deleted" else snapshot["id"]
    subject = f"Policy {snapshot['policy_number']}: {event.replace('_', ' ')} update"
    body = (
        "Hello,\n\n"
        f"Policy {snapshot['policy_number']} ({snapshot['product_name']}) with "
        f"{snapshot['company_name']} {POLICY_EVENT_TEXT[event]}.\n"
        f"Client: {snapshot['client_name']}\n"
        f"Coverage end date: {snapshot['end_date']}\n"
        f"Outstanding premium: ${snapshot['outstanding']:,.2f}\n"
    )
    if note:
        body += f"\n{note}\n"
    body += f"\n{SIGNATURE}"
    _log_and_send(
        snapshot["recipients"],
        notification_type or f"policy_{event}",
        subject,
        body,
        policy_id=policy_id,
    )


def send_expiry_reminders() -> int:
    """Email reminders for active policies ending in 30, 7 or 1 days.

    Run once a day (for example as a Railway cron job):
        flask send-expiry-reminders
    Reminders already logged today for the same policy are skipped.
    Returns the number of policies notified.
    """
    today = date.today()
    start_of_day = datetime.combine(today, datetime.min.time())
    notified = 0
    for days_before in (30, 7, 1):
        target_date = today + timedelta(days=days_before)
        notification_type = f"expiry_reminder_{days_before}_days"
        policies = Policy.query.filter(
            Policy.end_date == target_date,
            Policy.status == "active",
        ).all()
        for policy in policies:
            already_sent = NotificationLog.query.filter(
                NotificationLog.policy_id == policy.id,
                NotificationLog.notification_type == notification_type,
                NotificationLog.created_at >= start_of_day,
            ).first()
            if already_sent:
                continue
            snapshot = policy_snapshot(policy)
            notify_policy(
                snapshot,
                "expiring",
                note=(
                    f"Days remaining: {days_before}. "
                    "Please contact your agent if you wish to renew."
                ),
                notification_type=notification_type,
            )
            notified += 1
    return notified


# ==================== CLAIMS ====================

def notify_claim(claim, event: str = "status") -> None:
    """Email the client and account staff about a claim update."""
    client = claim.client_ref
    policy = claim.policy_ref
    status_label = (claim.status or "").replace("_", " ").title()
    recipients = _unique(client_emails(client) + staff_emails(claim.owner_id))
    subject = f"Claim {claim.claim_number}: {event} update"
    body = (
        "Hello,\n\n"
        f"Claim {claim.claim_number} on policy "
        f"{policy.policy_number if policy else ''} has been updated.\n"
        f"Client: {client.full_name() if client else ''}\n"
        f"Status: {status_label}\n"
        f"Claimed amount: ${(claim.claimed_amount or 0):,.2f}\n"
        f"Approved amount: ${(claim.approved_amount or 0):,.2f}\n"
        f"\n{SIGNATURE}"
    )
    _log_and_send(
        recipients,
        f"claim_{event}",
        subject,
        body,
        policy_id=claim.policy_id,
        claim_id=claim.id,
    )


# ==================== PASSWORD RESET ====================

def send_password_reset_email(user: User, reset_link: str) -> None:
    subject = "Reset your Ripple Capital password"
    body = (
        f"Hello {user.full_name},\n\n"
        "We received a request to reset your password. Use the link below to choose "
        "a new one. The link expires in 1 hour and can only be used once.\n\n"
        f"{reset_link}\n\n"
        "If you did not request this, you can ignore this email and your password "
        "will stay the same.\n\n"
        f"{SIGNATURE}"
    )
    _log_and_send([user.email], "password_reset", subject, body)



def safe_notify(fn, *args, **kwargs):
    """Run a notification without letting any error reach the user's request."""
    try:
        fn(*args, **kwargs)
    except Exception:
        db.session.rollback()
        logger.exception("Notification %s failed", getattr(fn, "__name__", fn))
