# policies/services.py
from datetime import date
from decimal import Decimal

from django.db import transaction

from .models import Policy, PremiumInstallment, PolicyStatus


def generate_installments(policy: Policy, num_installments: int = 4):
    """
    Split the policy premium into 'num_installments' equal installments
    over the policy period.

    Example: quarterly installments for annual policies.
    """
    if num_installments <= 0:
        num_installments = 1

    PremiumInstallment.objects.filter(policy=policy).delete()

    from dateutil.relativedelta import relativedelta  # optional dependency

    amount_per = (policy.premium_amount / Decimal(num_installments)).quantize(Decimal("0.01"))
    current_start = policy.start_date

    for i in range(num_installments):
        due_date = current_start + relativedelta(months=int(12 / num_installments) * i)
        PremiumInstallment.objects.create(
            policy=policy,
            installment_number=i + 1,
            due_date=due_date,
            amount_due=amount_per,
            amount_paid=Decimal("0.00"),
            balance=amount_per,
        )


@transaction.atomic
def renew_policy(policy: Policy, form) -> Policy:
    """
    Apply renewal terms to an existing policy instance.

    You could also choose to create a NEW policy record for each renewal.
    For now, we update the existing policy in-place.
    """
    if not form.is_valid():
        raise ValueError("Invalid renewal data")

    policy.sum_insured = form.cleaned_data["sum_insured"]
    policy.premium_amount = form.cleaned_data["premium_amount"]
    policy.commission_rate = form.cleaned_data["commission_rate"]
    policy.start_date = form.cleaned_data["start_date"]
    policy.end_date = form.cleaned_data["end_date"]
    policy.status = PolicyStatus.ACTIVE
    policy.save()

    # Regenerate installments for new period
    generate_installments(policy)
    return policy
