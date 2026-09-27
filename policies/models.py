# policies/models.py
from decimal import Decimal
from datetime import date

from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError


class PolicyStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    PENDING = "PENDING", "Pending"
    EXPIRED = "EXPIRED", "Expired"
    CANCELLED = "CANCELLED", "Cancelled"


class Policy(models.Model):
    """
    An insurance policy arranged by Ripple Capital between a client
    (policyholder) and an insurance company (underwriter).
    """

    policy_number = models.CharField(max_length=100, unique=True)
    client = models.ForeignKey(
        "clients.Client",
        on_delete=models.PROTECT,
        related_name="policies",
    )
    insurance_company = models.ForeignKey(
        "companies.InsuranceCompany",
        on_delete=models.PROTECT,
        related_name="policies",
    )
    class_of_business = models.ForeignKey(
        "companies.ClassOfBusiness",
        on_delete=models.PROTECT,
        related_name="policies",
    )
    sum_insured = models.DecimalField(max_digits=14, decimal_places=2)
    premium_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        help_text="Total premium (annual or total period) owed by client to insurer.",
    )
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Percentage commission Ripple Capital earns on this policy.",
    )

    start_date = models.DateField()
    end_date = models.DateField()

    status = models.CharField(
        max_length=20,
        choices=PolicyStatus.choices,
        default=PolicyStatus.ACTIVE,
    )

    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="policies_handled",
        help_text="Ripple Capital staff user who handled this policy.",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_date"]
        verbose_name = "Policy"
        verbose_name_plural = "Policies"
        indexes = [
            models.Index(fields=["policy_number"]),
        ]

    def __str__(self):
        return self.policy_number

    def clean(self):
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError(
                {"end_date": "Policy end date cannot be before start date."}
            )

    @property
    def commission_amount(self) -> Decimal:
        """
        Commission Ripple Capital expects to earn on this policy
        based on full premium.
        """
        return (self.premium_amount * self.commission_rate) / Decimal("100.00")

    @property
    def net_premium_to_insurer(self) -> Decimal:
        """
        Net premium (premium - commission) owed to the insurer.
        """
        return self.premium_amount - self.commission_amount

    def total_instalments_due(self) -> Decimal:
        from policies.models import PremiumInstallment
        return (
            self.installments.aggregate(total=models.Sum("amount_due"))["total"]
            or Decimal("0.00")
        )

    def total_instalments_paid(self) -> Decimal:
        from policies.models import PremiumInstallment
        return (
            self.installments.aggregate(total=models.Sum("amount_paid"))["total"]
            or Decimal("0.00")
        )

    def outstanding_premium(self) -> Decimal:
        from policies.models import PremiumInstallment
        return (
            self.installments.exclude(status="PAID").aggregate(
                total=models.Sum("balance")
            )["total"]
            or Decimal("0.00")
        )


class PremiumInstallment(models.Model):
    """
    A scheduled premium installment for a policy.

    Premium is owed by the client to the insurer. Ripple Capital collects
    this and earns commission separately.
    """

    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("PARTIAL", "Partially Paid"),
        ("PAID", "Paid"),
        ("OVERDUE", "Overdue"),
    ]

    policy = models.ForeignKey(
        Policy,
        on_delete=models.CASCADE,
        related_name="installments",
    )
    installment_number = models.PositiveIntegerField()
    due_date = models.DateField()
    amount_due = models.DecimalField(max_digits=14, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
    )

    class Meta:
        ordering = ["policy", "installment_number"]
        unique_together = ("policy", "installment_number")
        verbose_name = "Premium Installment"
        verbose_name_plural = "Premium Installments"

    def __str__(self):
        return f"{self.policy.policy_number} - Inst #{self.installment_number}"

    def clean(self):
        if self.amount_due < 0:
            raise ValidationError({"amount_due": "Amount due cannot be negative."})

    def update_status(self, today: date | None = None):
        """
        Update status based on balance and due date.
        """
        if today is None:
            today = date.today()

        if self.balance <= 0:
            self.status = "PAID"
            self.balance = Decimal("0.00")
        elif self.amount_paid > 0 and self.balance > 0:
            self.status = "PARTIAL"
        else:
            if self.due_date < today:
                self.status = "OVERDUE"
            else:
                self.status = "PENDING"

    def save(self, *args, **kwargs):
        if self.amount_due is not None and self.amount_paid is not None:
            self.balance = self.amount_due - self.amount_paid
        self.update_status()
        super().save(*args, **kwargs)
