"""
commissions/models.py

Core revenue models for Ripple Capital Private Limited's ERP.

Business context
-----------------
Ripple Capital acts as an insurance broker/agent. The premium a client
pays is NOT company revenue — it is a liability owed to the insurance
company (underwriter), tracked and eventually remitted via the
`disbursements` app. The ONLY real revenue Ripple Capital earns is the
commission percentage withheld from each premium payment.

This module tracks that commission end-to-end:

    Payment (premium received)
        --> Commission (revenue recognized, auto-calculated)
                --> CommissionAdjustment (reversal/correction, if needed)
                --> AgentCommissionPayout (internal incentive payout batch)

Design principles enforced here:
    1. Commission rows are never deleted — only adjusted via a linked
       CommissionAdjustment record, preserving a full audit trail.
    2. All monetary fields use Decimal, never float, to avoid rounding
       errors in financial calculations.
    3. A custom QuerySet/Manager centralizes common filtering logic
       so it's reused consistently across admin, views, services, and
       report generation — instead of duplicating .filter() calls.
"""

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum, Q
from django.core.exceptions import ValidationError
from django.utils import timezone


# ======================================================================
# STATUS CHOICES
# ======================================================================
class CommissionStatus(models.TextChoices):
    """
    Lifecycle of a single Commission record.

        PENDING   -> Just created from a payment, not yet reviewed.
        CONFIRMED -> Reviewed/approved by an accountant, safe to
                     include in revenue reports and payout calculations.
        REVERSED  -> Fully or partially reversed via a
                     CommissionAdjustment (e.g. payment was refunded,
                     cheque bounced, policy cancelled).
        SETTLED   -> Included in a finalized remittance (Disbursement)
                     batch to the insurance company. The insurer has
                     been paid their net premium share for this
                     payment, so Ripple Capital's commission on it is
                     now finalized/closed and should not be reversed
                     without a manual correction process.
    """
    PENDING = "PENDING", "Pending"
    CONFIRMED = "CONFIRMED", "Confirmed"
    REVERSED = "REVERSED", "Reversed"
    SETTLED = "SETTLED", "Settled"


class PayoutStatus(models.TextChoices):
    """Lifecycle of an AgentCommissionPayout batch."""
    PENDING = "PENDING", "Pending"
    PAID = "PAID", "Paid"


# ======================================================================
# CUSTOM QUERYSET / MANAGER
# ======================================================================
class CommissionQuerySet(models.QuerySet):
    """
    Reusable, chainable filters for the Commission model.

    Usage examples:
        Commission.objects.confirmed()
        Commission.objects.for_insurer(company).undisbursed()
        Commission.objects.for_agent(user).for_period(start, end)
    """

    def pending(self):
        return self.filter(status=CommissionStatus.PENDING)

    def confirmed(self):
        return self.filter(status=CommissionStatus.CONFIRMED)

    def reversed(self):
        return self.filter(status=CommissionStatus.REVERSED)

    def settled(self):
        return self.filter(status=CommissionStatus.SETTLED)

    def undisbursed(self):
        """
        Commissions that are confirmed but not yet linked to a
        Disbursement — i.e. the insurer has not yet been fully
        remitted their share for these payments.
        """
        return self.filter(disbursement__isnull=True).exclude(
            status=CommissionStatus.REVERSED
        )

    def unpaid_to_agent(self):
        """Commissions not yet bundled into an AgentCommissionPayout."""
        return self.filter(agent_payout__isnull=True).exclude(
            status=CommissionStatus.REVERSED
        )

    def for_insurer(self, insurance_company):
        return self.filter(policy__insurance_company=insurance_company)

    def for_agent(self, agent):
        return self.filter(policy__agent=agent)

    def for_client(self, client):
        return self.filter(policy__client=client)

    def for_period(self, start_date, end_date):
        return self.filter(created_at__date__range=(start_date, end_date))

    def total_amount(self):
        """
        Sum of the `amount` field across the current queryset.
        Returns Decimal('0.00') instead of None when empty, so callers
        never need to guard against NoneType arithmetic errors.
        """
        return self.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")


class CommissionManager(models.Manager.from_queryset(CommissionQuerySet)):
    """
    Manager wrapping CommissionQuerySet, with select_related applied
    by default to avoid N+1 queries in the vast majority of use-cases
    (list views, admin, reports all need policy/client/insurer data).
    """

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related(
                "policy",
                "policy__client",
                "policy__insurance_company",
                "policy__agent",
                "payment",
                "disbursement",
                "agent_payout",
            )
        )


# ======================================================================
# COMMISSION MODEL
# ======================================================================
class Commission(models.Model):
    """
    Represents commission revenue earned by Ripple Capital from a
    single premium payment.

    One Commission record is created automatically per Payment (see
    payments/signals.py), calculated as:

        amount = payment.amount * (policy.commission_rate / 100)

    This is a snapshot at time of creation — `rate` is stored here
    (not just referenced from policy) so that historical commission
    records remain accurate even if the policy's commission_rate is
    later changed for future transactions.
    """

    # ------------------------------------------------------------
    # SOURCE LINKS
    # ------------------------------------------------------------
    payment = models.OneToOneField(
        "payments.Payment",
        on_delete=models.PROTECT,
        related_name="commission",
        help_text="The premium payment this commission was calculated from.",
    )
    policy = models.ForeignKey(
        "policies.Policy",
        on_delete=models.PROTECT,
        related_name="commissions",
        help_text="The policy this commission relates to.",
    )

    # ------------------------------------------------------------
    # FINANCIAL FIELDS
    # ------------------------------------------------------------
    rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Commission rate (%) applied, snapshotted at creation time.",
    )
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        help_text="Commission amount earned (payment.amount * rate / 100).",
    )

    # ------------------------------------------------------------
    # STATUS & LIFECYCLE
    # ------------------------------------------------------------
    status = models.CharField(
        max_length=20,
        choices=CommissionStatus.choices,
        default=CommissionStatus.PENDING,
    )

    # ------------------------------------------------------------
    # DOWNSTREAM LINKS
    # ------------------------------------------------------------
    disbursement = models.ForeignKey(
        "disbursements.Disbursement",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="commission_items",
        help_text="Set once this commission has been bundled into a "
                   "remittance batch sent to the insurance company.",
    )
    agent_payout = models.ForeignKey(
        "AgentCommissionPayout",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="commission_items",
        help_text="Set once this commission has been bundled into an "
                   "internal agent incentive payout batch.",
    )

    # ------------------------------------------------------------
    # TIMESTAMPS
    # ------------------------------------------------------------
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    objects = CommissionManager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Commission"
        verbose_name_plural = "Commissions"
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["policy"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=Q(amount__gte=0),
                name="commission_amount_non_negative",
            ),
            models.CheckConstraint(
                check=Q(rate__gte=0) & Q(rate__lte=100),
                name="commission_rate_between_0_and_100",
            ),
        ]

    def __str__(self):
        return f"Commission #{self.pk} — {self.policy.policy_number} (KES {self.amount})"

    # ------------------------------------------------------------
    # COMPUTED PROPERTIES
    # ------------------------------------------------------------
    @property
    def total_adjustments(self):
        """
        Sum of all adjustment amounts linked to this commission.
        Adjustment amounts are stored as signed values (negative for
        reversals/reductions), so this can be added directly to
        `amount` to get the true net figure.
        """
        return self.adjustments.aggregate(
            total=Sum("adjustment_amount")
        )["total"] or Decimal("0.00")

    @property
    def net_amount(self):
        """
        The true commission amount after accounting for any reversals
        or corrections. This is the figure that should be used in
        financial reports and disbursement calculations — NOT the raw
        `amount` field, which represents the original calculation only.
        """
        return self.amount + self.total_adjustments

    @property
    def is_settled(self):
        """True if this commission has been linked to a remittance batch."""
        return self.disbursement_id is not None

    @property
    def is_paid_to_agent(self):
        return self.agent_payout_id is not None

    # ------------------------------------------------------------
    # STATE TRANSITION HELPERS
    # ------------------------------------------------------------
    def mark_confirmed(self, save=True):
        """
        Move this commission from PENDING to CONFIRMED, recording the
        timestamp. Confirmed commissions are eligible for inclusion in
        disbursements and agent payouts.
        """
        if self.status != CommissionStatus.PENDING:
            raise ValidationError(
                f"Cannot confirm a commission with status '{self.status}'. "
                "Only PENDING commissions can be confirmed."
            )
        self.status = CommissionStatus.CONFIRMED
        self.confirmed_at = timezone.now()
        if save:
            self.save(update_fields=["status", "confirmed_at"])

    def mark_settled(self, disbursement, save=True):
        """
        Link this commission to a finalized Disbursement batch and
        mark it as SETTLED.

        Meaning: the insurer has been paid their net premium share for
        this payment, so Ripple Capital's commission on it is now
        finalized/closed.
        """
        if self.status == CommissionStatus.REVERSED:
            raise ValidationError(
                "Cannot settle a commission that has been reversed."
            )
        self.disbursement = disbursement
        self.status = CommissionStatus.SETTLED
        if save:
            self.save(update_fields=["disbursement", "status"])

    def clean(self):
        """
        Model-level validation, run by ModelForm.is_valid() and can be
        explicitly called via full_clean() in services before saving.
        """
        if self.rate is not None and (self.rate < 0 or self.rate > 100):
            raise ValidationError({"rate": "Commission rate must be between 0 and 100."})
        if self.amount is not None and self.amount < 0:
            raise ValidationError({"amount": "Commission amount cannot be negative."})


# ======================================================================
# COMMISSION ADJUSTMENT MODEL
# ======================================================================
class AdjustmentReason(models.TextChoices):
    """Predefined reasons for auditability and reporting consistency."""
    PAYMENT_REVERSED = "PAYMENT_REVERSED", "Underlying payment reversed"
    PAYMENT_REFUNDED = "PAYMENT_REFUNDED", "Client refunded"
    POLICY_CANCELLED = "POLICY_CANCELLED", "Policy cancelled"
    CALCULATION_ERROR = "CALCULATION_ERROR", "Calculation error correction"
    RATE_CORRECTION = "RATE_CORRECTION", "Commission rate correction"
    OTHER = "OTHER", "Other (see notes)"


class CommissionAdjustment(models.Model):
    """
    An immutable audit entry representing a correction or reversal
    applied to a Commission record.

    IMPORTANT: Commission.amount is never edited directly once created.
    Instead, corrections are always recorded here as a signed delta
    (negative to reduce, positive to increase), and Commission.net_amount
    reflects the true, corrected figure. This mirrors standard
    double-entry accounting practice: never overwrite history, always
    post a correcting entry.
    """

    commission = models.ForeignKey(
        Commission,
        on_delete=models.CASCADE,
        related_name="adjustments",
    )
    reason = models.CharField(
        max_length=30,
        choices=AdjustmentReason.choices,
        default=AdjustmentReason.OTHER,
    )
    notes = models.TextField(
        blank=True,
        help_text="Additional context, especially required when reason='OTHER'.",
    )
    adjustment_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        help_text="Signed amount. Use a negative value to reduce/reverse "
                   "commission revenue, positive to add a correction.",
    )
    adjusted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="commission_adjustments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Commission Adjustment"
        verbose_name_plural = "Commission Adjustments"

    def __str__(self):
        sign = "+" if self.adjustment_amount >= 0 else ""
        return f"Adjustment on Commission #{self.commission_id}: {sign}{self.adjustment_amount}"

    def clean(self):
        if self.reason == AdjustmentReason.OTHER and not (self.notes or "").strip():
            raise ValidationError(
                {"notes": "Notes are required when reason is 'Other'."}
            )
        if self.adjustment_amount == 0:
            raise ValidationError(
                {"adjustment_amount": "Adjustment amount cannot be zero."}
            )


# ======================================================================
# AGENT COMMISSION PAYOUT MODEL
# ======================================================================
class AgentCommissionPayout(models.Model):
    """
    Represents a batch payout of internal incentive commission owed
    TO an agent (staff member who sold the policy), separate from the
    money owed BY Ripple Capital TO the insurance company (which is
    handled in the disbursements app).

    This lets Ripple Capital reward its own sales agents with a share
    of the commission revenue generated by policies they brought in,
    tracked and paid out periodically (e.g. monthly).
    """

    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="commission_payouts",
        limit_choices_to={"role": "AGENT"},
    )
    period_start = models.DateField()
    period_end = models.DateField()

    total_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Sum of all commission_items linked to this payout batch. "
                   "Recalculated via recalculate_total().",
    )

    status = models.CharField(
        max_length=20,
        choices=PayoutStatus.choices,
        default=PayoutStatus.PENDING,
    )

    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="commission_payouts_processed",
        help_text="The accountant/admin who confirmed this payout was paid.",
    )
    paid_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-period_start"]
        verbose_name = "Agent Commission Payout"
        verbose_name_plural = "Agent Commission Payouts"
        constraints = [
            models.UniqueConstraint(
                fields=["agent", "period_start", "period_end"],
                name="unique_agent_payout_per_period",
            ),
            models.CheckConstraint(
                check=Q(period_end__gte=models.F("period_start")),
                name="payout_period_end_after_start",
            ),
        ]

    def __str__(self):
        return (
            f"Payout to {self.agent.get_full_name() or self.agent.username} "
            f"({self.period_start} → {self.period_end}) — KES {self.total_amount}"
        )

    def clean(self):
        if self.period_end and self.period_start and self.period_end < self.period_start:
            raise ValidationError(
                {"period_end": "Period end date cannot be before period start date."}
            )

    def recalculate_total(self, save=True):
        """
        Recomputes total_amount from the actual linked Commission
        records (commission_items), rather than trusting a manually
        entered figure. Should be called after attaching/detaching
        commission items to keep this in sync.
        """
        total = self.commission_items.aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0.00")
        self.total_amount = total
        if save:
            self.save(update_fields=["total_amount"])
        return total

    def mark_paid(self, user, save=True):
        """
        Marks this payout batch as paid, recording who confirmed it
        and when. Should be called from a service function that also
        handles any external payment integration (e.g. bank transfer
        API), not directly from a view.
        """
        if self.status == PayoutStatus.PAID:
            raise ValidationError("This payout has already been marked as paid.")
        self.status = PayoutStatus.PAID
        self.paid_by = user
        self.paid_at = timezone.now()
        if save:
            self.save(update_fields=["status", "paid_by", "paid_at"])

