# clients/models.py
from django.db import models
from django.conf import settings
from django.db.models import Sum


class ClientType(models.TextChoices):
    INDIVIDUAL = "INDIVIDUAL", "Individual"
    CORPORATE = "CORPORATE", "Corporate"


class Client(models.Model):
    """
    Represents a policyholder / premium payer.

    Ripple Capital is the broker; each client buys policies via Ripple
    Capital from various insurance companies.
    """
    client_type = models.CharField(
        max_length=20,
        choices=ClientType.choices,
        default=ClientType.INDIVIDUAL,
    )
    full_name = models.CharField(max_length=255)
    id_number = models.CharField(
        max_length=50,
        blank=True,
        help_text="National ID / Registration number (optional but recommended).",
    )
    tax_pin = models.CharField(
        max_length=50,
        blank=True,
        help_text="Tax PIN / KRA PIN (optional).",
    )
    email = models.EmailField(blank=True)
    phone_number = models.CharField(max_length=20)
    address = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="clients_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["full_name"]
        verbose_name = "Client"
        verbose_name_plural = "Clients"

    def __str__(self):
        return self.full_name

    def total_outstanding(self):
        """
        Sum of balances on all non-paid installments across all policies.
        """
        from policies.models import PremiumInstallment  # local import to avoid circular
        return (
            PremiumInstallment.objects.filter(
                policy__client=self,
            )
            .exclude(status="PAID")
            .aggregate(total=Sum("balance"))["total"]
            or 0
        )

    def total_premium_paid(self):
        """
        Total premium paid by this client (all payments).
        Note: The premium belongs to insurers; this is informational only.
        """
        from payments.models import Payment
        return (
            Payment.objects.filter(
                installment__policy__client=self
            ).aggregate(total=Sum("amount"))["total"]
            or 0
        )

    def active_policies(self):
        """
        Returns queryset of active policies for this client.
        """
        from policies.models import Policy
        return Policy.objects.filter(client=self, status="ACTIVE")
