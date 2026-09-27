"""
notifications/tasks.py

Celery tasks for sending premium due and overdue reminders.

These tasks are designed to run periodically (e.g. daily) via Celery Beat.
They scan the PremiumInstallment table and send email reminders to clients
about upcoming or overdue premiums.

Business context
----------------
Ripple Capital is the broker/agent. It collects premiums from clients
on behalf of various insurance companies (underwriters). This module
handles the communication side:

    - Premium due reminders: sent a few days before due date.
    - Premium overdue reminders: sent after the due date has passed.

Premiums belong to the insurers; Ripple Capital's revenue is commission.
These reminders are about the CLIENT's obligation to PAY PREMIUM to
the INSURER via Ripple Capital.

Configuration
-------------
In settings.py, define Celery Beat schedule (example):

    CELERY_BEAT_SCHEDULE = {
        "send-upcoming-premium-reminders": {
            "task": "notifications.tasks.send_upcoming_premium_reminders",
            "schedule": 86400.0,  # every 24 hours
            "args": (5,),         # days_ahead
        },
        "send-overdue-premium-reminders": {
            "task": "notifications.tasks.send_overdue_premium_reminders",
            "schedule": 86400.0,  # every 24 hours
        },
    }

You can adjust 'days_ahead' depending on how much notice you want to give clients.
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from policies.models import PremiumInstallment
from notifications.services import (
    send_premium_due_email,
    send_premium_overdue_email,
)

logger = logging.getLogger("notifications")


def _get_today():
    """
    Wrapper for timezone-aware 'today' (date only).
    Easier to mock in tests if needed.
    """
    return timezone.now().date()


@shared_task
def send_upcoming_premium_reminders(days_ahead: int = 5) -> int:
    """
    Send premium DUE reminders for installments that are 'days_ahead'
    days away from the due date.

    Args:
        days_ahead: How many days before the due date a reminder should be sent.

    Returns:
        The number of reminders sent.

    Logic:
        - target_date = today + days_ahead
        - Find installments with:
              due_date == target_date
              status in ["PENDING", "PARTIAL"] (adjust to your model)
        - For each installment:
              send_premium_due_email(...)
        - Skip installments whose clients do not have an email address.
    """
    today = _get_today()
    target_date = today + timedelta(days=days_ahead)

    # Adjust status choices to match your PremiumInstallment model.
    # Here we assume status choices: PENDING, PARTIAL, PAID, OVERDUE
    qs = PremiumInstallment.objects.filter(
        due_date=target_date,
        status__in=["PENDING", "PARTIAL"],
    ).select_related("policy__client", "policy__insurance_company")

    sent_count = 0
    for inst in qs:
        try:
            log = send_premium_due_email(inst)
            if log is not None:
                sent_count += 1
        except Exception as exc:  # be defensive; never crash the entire batch
            logger.exception(
                "Error sending premium due reminder for installment %s (policy %s): %s",
                inst.id,
                inst.policy.policy_number,
                exc,
            )

    logger.info(
        "Premium due reminders task completed: %s reminder(s) sent for due date %s",
        sent_count,
        target_date,
    )
    return sent_count


@shared_task
def send_overdue_premium_reminders() -> int:
    """
    Send premium OVERDUE reminders for installments whose due_date
    has passed and are not fully paid.

    Returns:
        The number of reminders sent.

    Logic:
        - today = current date
        - Find installments with:
              due_date < today
              status in ["PENDING", "PARTIAL", "OVERDUE"]
        - For each installment:
              send_premium_overdue_email(...)
        - Skip installments whose clients do not have an email address.
    """
    today = _get_today()

    qs = PremiumInstallment.objects.filter(
        due_date__lt=today,
        status__in=["PENDING", "PARTIAL", "OVERDUE"],
    ).select_related("policy__client", "policy__insurance_company")

    sent_count = 0
    for inst in qs:
        try:
            log = send_premium_overdue_email(inst)
            if log is not None:
                sent_count += 1
        except Exception as exc:
            logger.exception(
                "Error sending premium overdue notice for installment %s (policy %s): %s",
                inst.id,
                inst.policy.policy_number,
                exc,
            )

    logger.info(
        "Premium overdue reminders task completed: %s reminder(s) sent for overdue installments as of %s",
        sent_count,
        today,
    )
    return sent_count
