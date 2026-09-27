# payments/signals.py
from decimal import Decimal
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Payment
from policies.models import PremiumInstallment
from commissions.models import Commission
from policies.models import Policy


@receiver(post_save, sender=Payment)
def update_installment_and_commission(sender, instance: Payment, created, **kwargs):
    """
    When a new Payment is created:
    - Update the related PremiumInstallment's amount_paid / balance / status.
    - Create a Commission record (Ripple Capital's revenue).

    This is the core link from premiums (liability) to commissions (revenue).
    """
    if not created:
        return

    installment: PremiumInstallment = instance.installment
    # Update installment
    installment.amount_paid += instance.amount
    installment.balance = installment.amount_due - installment.amount_paid

    # Update status logic according to your PremiumInstallment model
    if installment.balance <= 0:
        installment.status = "PAID"
        installment.balance = Decimal("0.00")
    elif installment.amount_paid > 0 and installment.balance > 0:
        installment.status = "PARTIAL"
    # else leave as PENDING/OVERDUE depending on due_date logic in model.save()

    installment.save()

    # Create commission
    policy: Policy = installment.policy
    rate = policy.commission_rate
    commission_amount = (instance.amount * rate) / Decimal("100")

    Commission.objects.create(
        payment=instance,
        policy=policy,
        rate=rate,
        amount=commission_amount,
    )
