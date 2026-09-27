# companies/models.py
from decimal import Decimal
from django.db import models


class InsuranceCompany(models.Model):
    """
    An insurance company (underwriter) that Ripple Capital brokers for.
    """
    name = models.CharField(max_length=200, unique=True)
    short_code = models.CharField(
        max_length=20,
        unique=True,
        help_text="Short code for internal reference (e.g. 'CIC', 'BRITAM').",
    )
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=50, blank=True)
    address = models.TextField(blank=True)
    bank_account_details = models.TextField(
        blank=True,
        help_text="Bank account details used when Ripple Capital remits premiums.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Uncheck if Ripple Capital no longer works with this insurer.",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Insurance Company"
        verbose_name_plural = "Insurance Companies"

    def __str__(self):
        return self.name

    def default_commission_rate_for(self, class_name: str) -> Decimal | None:
        """
        Convenience method to get default commission rate for a
        specific class of business by name.
        """
        cob = self.classes.filter(name__iexact=class_name).first()
        return cob.default_commission_rate if cob else None


class ClassOfBusiness(models.Model):
    """
    A line of business under an insurance company (e.g. Motor, Fire, Marine).
    Holds a default commission rate Ripple Capital earns on that class.
    """
    insurance_company = models.ForeignKey(
        InsuranceCompany,
        on_delete=models.CASCADE,
        related_name="classes",
    )
    name = models.CharField(max_length=100)
    default_commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Default commission percentage (e.g. 10.00 for 10%).",
    )

    class Meta:
        unique_together = ("insurance_company", "name")
        ordering = ["insurance_company__name", "name"]
        verbose_name = "Class of Business"
        verbose_name_plural = "Classes of Business"

    def __str__(self):
        return f"{self.insurance_company.short_code} - {self.name}"
