"""
commissions/services.py

Business logic layer for the Commissions app.

Why a services layer?
----------------------
Views should never contain financial logic directly. By centralizing
every commission state-change and calculation here:

    1. Views stay thin (just call a service function, handle the
       response).
    2. Celery tasks, management commands, and the Django admin can
       all reuse the exact same logic — no duplicated business rules.
    3. Every function here that mutates data wraps its work in an
       atomic transaction, so a failure halfway through never leaves
       the database in an inconsistent state (e.g. a payout marked
       paid but its commission items not linked).
    4. Each function is independently unit-testable without needing
       to simulate an HTTP request.

All monetary values are Decimal throughout — never float.
"""

import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum, Count, Q
from django.utils import timezone

from .models import (
    Commission,
    CommissionStatus,
    CommissionAdjustment,
    AdjustmentReason,
    AgentCommissionPayout,
    PayoutStatus,
)

logger = logging.getLogger("commissions")


# ======================================================================
# EXCEPTIONS
# ======================================================================
class CommissionServiceError(Exception):
    """Raised for business-rule violations within this service layer.

    Kept distinct from Django's ValidationError so callers (views,
    API endpoints) can catch this specifically and show a clean
    user-facing message, rather than leaking model-level errors.
    """
    pass


# ======================================================================
# CONFIRMATION
# ======================================================================
@transaction.atomic
def confirm_commission(commission: Commission, user) -> Commission:
    """
    Move a single Commission from PENDING to CONFIRMED.

    Confirmation represents an accountant/admin having reviewed the
    commission (e.g. verified the payment actually cleared) and
    approved it as legitimate revenue, eligible for inclusion in
    remittance (disbursement) batches and agent payouts.
    """
    if commission.status != CommissionStatus.PENDING:
        raise CommissionServiceError(
            f"Commission #{commission.pk} cannot be confirmed — "
            f"current status is '{commission.get_status_display()}'."
        )

    commission.mark_confirmed(save=True)

    logger.info(
        "Commission #%s confirmed by %s (amount=%s)",
        commission.pk, getattr(user, "username", "system"), commission.amount,
    )
    return commission


@transaction.atomic
def bulk_confirm_commissions(commission_ids, user) -> int:
    """
    Confirm multiple commissions at once (e.g. from an admin bulk
    action or a "confirm all pending" button in a dashboard).

    Returns the number of commissions actually confirmed. Silently
    skips any commissions that are not in PENDING status, rather than
    raising — since bulk operations should be resilient to a mixed
    selection (some already confirmed, some pending).
    """
    queryset = Commission.objects.select_for_update().filter(
        pk__in=commission_ids, status=CommissionStatus.PENDING
    )

    count = 0
    now = timezone.now()
    for commission in queryset:
        commission.status = CommissionStatus.CONFIRMED
        commission.confirmed_at = now
        commission.save(update_fields=["status", "confirmed_at"])
        count += 1

    logger.info(
        "%s commission(s) bulk-confirmed by %s",
        count, getattr(user, "username", "system"),
    )
    return count


# ======================================================================
# REVERSAL / ADJUSTMENT
# ======================================================================
@transaction.atomic
def reverse_commission(
    commission: Commission,
    *,
    reason: str,
    user,
    notes: str = "",
    amount: Decimal | None = None,
) -> CommissionAdjustment:
    """
    Reverse a commission fully or partially by creating a signed
    CommissionAdjustment, and updating the Commission's status.

    Args:
        commission: The Commission record to reverse.
        reason: One of AdjustmentReason choices.
        user: The staff member performing the reversal (for audit trail).
        notes: Required if reason == AdjustmentReason.OTHER.
        amount: Optional. If provided, must be a POSITIVE Decimal
                representing how much to reverse (a partial reversal).
                If omitted, the FULL remaining net_amount is reversed.

    Returns:
        The created CommissionAdjustment instance.

    Raises:
        CommissionServiceError: if the commission is already SETTLED
            (settled commissions are tied to a completed remittance
            batch; reversing them requires a manual correction process
            involving the insurer), or already fully reversed.
    """
    if commission.status == CommissionStatus.SETTLED:
        raise CommissionServiceError(
            f"Commission #{commission.pk} has already been settled as part of a "
            "remittance batch to the insurer and cannot be reversed directly. "
            "A manual correction process involving the insurance company is "
            "required."
        )

    if commission.status == CommissionStatus.REVERSED and amount is None:
        raise CommissionServiceError(
            f"Commission #{commission.pk} has already been fully reversed."
        )

    remaining = commission.net_amount
    if remaining <= 0:
        raise CommissionServiceError(
            f"Commission #{commission.pk} has no remaining balance to reverse."
        )

    if amount is None:
        reversal_amount = remaining
    else:
        if amount <= 0:
            raise CommissionServiceError("Reversal amount must be a positive value.")
        if amount > remaining:
            raise CommissionServiceError(
                f"Cannot reverse {amount} — only {remaining} remains on this commission."
            )
        reversal_amount = amount

    adjustment = CommissionAdjustment(
        commission=commission,
        reason=reason,
        notes=notes,
        adjustment_amount=-reversal_amount,  # stored as a negative delta
        adjusted_by=user,
    )
    adjustment.full_clean()
    adjustment.save()

    # If this reversal brings the net amount down to zero, mark the
    # commission as fully REVERSED. Otherwise leave status as-is
    # (a partial reversal doesn't necessarily invalidate the whole
    # commission — e.g. CONFIRMED stays CONFIRMED with a lower net_amount).
    if commission.net_amount <= 0:
        commission.status = CommissionStatus.REVERSED
        commission.save(update_fields=["status"])

    logger.warning(
        "Commission #%s reversed by %s: -%s (reason=%s)",
        commission.pk, getattr(user, "username", "system"), reversal_amount, reason,
    )
    return adjustment


@transaction.atomic
def add_manual_adjustment(
    commission: Commission,
    *,
    amount: Decimal,
    reason: str,
    user,
    notes: str = "",
) -> CommissionAdjustment:
    """
    Record a correction that is NOT a full reversal — e.g. the original
    commission was calculated with a slightly wrong rate and needs a
    positive top-up, or a rounding correction is needed.

    Unlike reverse_commission(), this accepts a signed `amount`
    directly (positive to increase, negative to decrease) and does
    not force the commission into REVERSED status.
    """
    if amount == 0:
        raise CommissionServiceError("Adjustment amount cannot be zero.")

    if commission.net_amount + amount < 0:
        raise CommissionServiceError(
            "This adjustment would push the commission's net amount below zero. "
            "Use reverse_commission() instead if the intent is a full/partial reversal."
        )

    adjustment = CommissionAdjustment(
        commission=commission,
        reason=reason,
        notes=notes,
        adjustment_amount=amount,
        adjusted_by=user,
    )
    adjustment.full_clean()
    adjustment.save()

    logger.info(
        "Manual adjustment of %s applied to Commission #%s by %s (reason=%s)",
        amount, commission.pk, getattr(user, "username", "system"), reason,
    )
    return adjustment


# ======================================================================
# AGENT PAYOUT GENERATION
# ======================================================================
@transaction.atomic
def generate_agent_payout(agent, period_start, period_end, user) -> AgentCommissionPayout:
    """
    Bundle all CONFIRMED, unpaid-to-agent commissions earned by
    a given agent within a date range into a new AgentCommissionPayout
    batch, ready to be reviewed and paid out.

    Args:
        agent: The User (role=AGENT) to generate a payout for.
        period_start, period_end: date objects defining the period.
        user: The admin/accountant triggering this generation.

    Raises:
        CommissionServiceError: if no eligible commissions exist for
            this agent/period, or if a payout for this exact period
            already exists for this agent.
    """
    if period_end < period_start:
        raise CommissionServiceError("period_end cannot be before period_start.")

    if AgentCommissionPayout.objects.filter(
        agent=agent, period_start=period_start, period_end=period_end
    ).exists():
        raise CommissionServiceError(
            f"A payout for {agent.get_full_name() or agent.username} covering "
            f"{period_start} to {period_end} already exists."
        )

    eligible_commissions = (
        Commission.objects.confirmed()
        .for_agent(agent)
        .for_period(period_start, period_end)
        .filter(agent_payout__isnull=True)
    )

    if not eligible_commissions.exists():
        raise CommissionServiceError(
            f"No eligible confirmed commissions found for "
            f"{agent.get_full_name() or agent.username} between "
            f"{period_start} and {period_end}."
        )

    payout = AgentCommissionPayout.objects.create(
        agent=agent,
        period_start=period_start,
        period_end=period_end,
        status=PayoutStatus.PENDING,
    )

    updated_count = eligible_commissions.update(agent_payout=payout)
    payout.recalculate_total(save=True)

    logger.info(
        "Payout #%s generated for agent %s: %s commission(s), total=%s",
        payout.pk, agent.username, updated_count, payout.total_amount,
    )
    return payout


@transaction.atomic
def generate_payouts_for_all_agents(period_start, period_end, user) -> list[AgentCommissionPayout]:
    """
    Convenience wrapper to generate payout batches for every agent who
    has at least one eligible commission in the given period. Agents
    with zero eligible commissions are silently skipped.

    Returns a list of the AgentCommissionPayout instances created.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()

    eligible_agent_ids = (
        Commission.objects.confirmed()
        .for_period(period_start, period_end)
        .filter(agent_payout__isnull=True, policy__agent__isnull=False)
        .values_list("policy__agent", flat=True)
        .distinct()
    )

    created_payouts = []
    for agent in User.objects.filter(pk__in=eligible_agent_ids):
        try:
            payout = generate_agent_payout(agent, period_start, period_end, user)
            created_payouts.append(payout)
        except CommissionServiceError as exc:
            logger.warning("Skipped payout generation for %s: %s", agent.username, exc)
            continue

    return created_payouts


@transaction.atomic
def mark_payout_paid(payout: AgentCommissionPayout, user) -> AgentCommissionPayout:
    """
    Confirm that an AgentCommissionPayout batch has actually been paid
    out to the agent (e.g. via bank transfer, mobile money, or cash).

    This does NOT integrate with an actual payment gateway — it simply
    records the confirmation. If/when you integrate M-Pesa B2C or a
    bank API for automatic agent payouts, that integration call should
    happen BEFORE this function is invoked, and this function should
    only run once the transfer is confirmed successful.
    """
    if payout.status == PayoutStatus.PAID:
        raise CommissionServiceError(
            f"Payout #{payout.pk} has already been marked as paid."
        )

    payout.mark_paid(user=user, save=True)

    logger.info(
        "Payout #%s to %s marked as PAID by %s (amount=%s)",
        payout.pk, payout.agent.username, getattr(user, "username", "system"),
        payout.total_amount,
    )
    return payout


# ======================================================================
# REPORTING / AGGREGATION
# ======================================================================
def get_commission_summary(start_date=None, end_date=None, insurance_company=None) -> dict:
    """
    High-level summary figures for the financial dashboard.

    Returns a dict with:
        total_earned        - sum of CONFIRMED + SETTLED commission amounts
        total_pending       - sum of PENDING commission amounts (awaiting review)
        total_reversed      - sum of reversed adjustment amounts (as a positive figure)
        total_undisbursed   - confirmed commissions not yet linked to a remittance batch
        total_unpaid_agents - confirmed commissions not yet paid out to agents
        commission_count    - total number of commission records in scope
    """
    qs = Commission.objects.all()

    if start_date and end_date:
        qs = qs.for_period(start_date, end_date)
    if insurance_company:
        qs = qs.for_insurer(insurance_company)

    total_earned = qs.filter(
        status__in=[CommissionStatus.CONFIRMED, CommissionStatus.SETTLED]
    ).total_amount()

    total_pending = qs.pending().total_amount()

    total_reversed = (
        CommissionAdjustment.objects.filter(commission__in=qs)
        .aggregate(total=Sum("adjustment_amount"))["total"]
        or Decimal("0.00")
    )
    # Adjustments are stored as negative deltas for reversals; report
    # as a positive "amount reversed" figure for readability.
    total_reversed_display = abs(total_reversed) if total_reversed < 0 else Decimal("0.00")

    total_undisbursed = qs.confirmed().undisbursed().total_amount()
    total_unpaid_agents = qs.confirmed().unpaid_to_agent().total_amount()

    return {
        "total_earned": total_earned,
        "total_pending": total_pending,
        "total_reversed": total_reversed_display,
        "total_undisbursed": total_undisbursed,
        "total_unpaid_agents": total_unpaid_agents,
        "commission_count": qs.count(),
    }


def get_commission_breakdown_by_insurer(start_date=None, end_date=None):
    """
    Returns a queryset of dicts, one row per insurance company, with
    total commission earned — used for the "per-insurer" section of
    the financial dashboard and for cross-checking against remittance
    obligations.
    """
    qs = Commission.objects.confirmed()
    if start_date and end_date:
        qs = qs.for_period(start_date, end_date)

    return (
        qs.values("policy__insurance_company__id", "policy__insurance_company__name")
        .annotate(
            total_commission=Sum("amount"),
            commission_count=Count("id"),
        )
        .order_by("-total_commission")
    )


def get_commission_breakdown_by_agent(start_date=None, end_date=None):
    """
    Returns a queryset of dicts, one row per agent, with total
    commission generated and how much remains unpaid to them —
    used for the agent leaderboard / incentive review dashboard.
    """
    qs = Commission.objects.confirmed()
    if start_date and end_date:
        qs = qs.for_period(start_date, end_date)

    return (
        qs.values("policy__agent__id", "policy__agent__first_name", "policy__agent__last_name")
        .annotate(
            total_commission=Sum("amount"),
            unpaid_commission=Sum(
                "amount", filter=Q(agent_payout__isnull=True)
            ),
            commission_count=Count("id"),
        )
        .order_by("-total_commission")
    )


def get_agent_payout_history(agent, limit=12):
    """
    Returns the most recent AgentCommissionPayout batches for a given
    agent, newest first — used on the agent's own dashboard so they
    can see their payout history.
    """
    return (
        AgentCommissionPayout.objects.filter(agent=agent)
        .order_by("-period_start")[:limit]
    )


def get_outstanding_commission_for_disbursement(insurance_company, up_to_date=None):
    """
    Returns confirmed, unsettled commissions for a specific insurer
    up to a given date — this is the exact queryset the disbursements
    app should use as the basis for generating a new remittance batch,
    ensuring commissions and disbursements always stay perfectly in sync.
    """
    qs = Commission.objects.confirmed().undisbursed().for_insurer(insurance_company)
    if up_to_date:
        qs = qs.filter(created_at__date__lte=up_to_date)
    return qs
