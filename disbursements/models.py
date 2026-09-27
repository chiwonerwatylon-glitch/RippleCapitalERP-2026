# disbursements/models.py
from decimal import Decimal
from django.db import models
from django.conf import settings


class DisbursementStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    PROCESSED = "PROCESSED", "Processed"


class Disbursement(models.Model):
    """
    Represents a remittance batch from Ripple Capital (broker) to one
    insurance company, covering all payments in a given period.

    NOTE:
    - total_premium_collected = money collected from clients for this insurer.
    - total_commission        = Ripple Capital's revenue on these premiums.
    - net_amount_payable      = total_premium_collected - total_commission
                                (amount owed to the insurer).
    """

    insurance_company = models.ForeignKey(
        "companies.InsuranceCompany",
        on_delete=models.PROTECT,
        related_name="disbursements",
    )
    period_start = models.DateField()
    period_end = models.DateField()

    total_premium_collected = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    total_commission = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    net_amount_payable = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Amount remitted to insurer (premium - commission).",
    )

    status = models.CharField(
        max_length=20,
        choices=DisbursementStatus.choices,
        default=DisbursementStatus.PENDING,
    )

    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="disbursements_processed",
    )
    processed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-period_start", "-period_end"]
        verbose_name = "Disbursement"
        verbose_name_plural = "Disbursements"
        constraints = [
            models.CheckConstraint(
                check=models.Q(period_end__gte=models.F("period_start")),
                name="disb_period_end_after_start",
            ),
        ]

    def __str__(self):
        return f"Disbursement to {self.insurance_company.name} ({self.period_start} → {self.period_end})"

    def recalculate_from_commissions(self):
        """
        Optional helper: recompute totals from linked commissions if
        you ever need to repair data. Normally handled by services.
        """
        from django.db.models import Sum

        commissions = self.commission_items.all()
        total_commission = commissions.aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0.00")

        # We don't have premium per commission here; total_premium_collected
        # is set when the disbursement is generated from Payments.
        self.total_commission = total_commission
        self.net_amount_payable = self.total_premium_collected - total_commission
        self.save(update_fields=["total_commission", "net_amount_payable"])
