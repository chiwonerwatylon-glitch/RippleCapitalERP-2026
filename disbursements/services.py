# disbursements/services.py
from decimal import Decimal
import logging

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import Disbursement, DisbursementStatus
from commissions.models import Commission
from payments.models import Payment

logger = logging.getLogger("disbursements")


class DisbursementServiceError(Exception):
    pass


@transaction.atomic
def generate_disbursement(insurance_company, period_start, period_end, user) -> Disbursement:
    """
    Generate a disbursement for a specific insurer and date range.

    Logic:
    - Find all payments for this insurer in the period.
    - Sum total payment amount (premium collected).
    - Sum all related commission amounts (company revenue).
    - net_amount_payable = total_premium_collected - total_commission.
    - Create Disbursement.
    - Link all relevant Commissions to this Disbursement and mark them as SETTLED.

    Note: Commissions use CommissionStatus; here we only link & mark them.
    """
    if period_end < period_start:
        raise DisbursementServiceError("period_end cannot be before period_start.")

    # Payments for policies under this insurer
    payments_qs = Payment.objects.filter(
        installment__policy__insurance_company=insurance_company,
        payment_date__date__range=(period_start, period_end),
    )

    if not payments_qs.exists():
        raise DisbursementServiceError(
            f"No payments found for {insurance_company.name} in the selected period."
        )

    total_premium = payments_qs.aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0.00")

    # Commissions from those payments
    commissions_qs = Commission.objects.confirmed().filter(
        payment__in=payments_qs,
        disbursement__isnull=True,  # not already linked
    )

    if not commissions_qs.exists():
        raise DisbursementServiceError(
            f"No eligible commissions found for {insurance_company.name} in the selected period."
        )

    total_commission = commissions_qs.aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0.00")

    disbursement = Disbursement.objects.create(
        insurance_company=insurance_company,
        period_start=period_start,
        period_end=period_end,
        total_premium_collected=total_premium,
        total_commission=total_commission,
        net_amount_payable=total_premium - total_commission,
        status=DisbursementStatus.PENDING,
        processed_by=user,
        processed_at=None,
    )

    # Link commissions & mark them as SETTLED
    from commissions.models import CommissionStatus

    for c in commissions_qs.select_for_update():
        c.disbursement = disbursement
        if c.status != CommissionStatus.REVERSED:
            c.status = CommissionStatus.SETTLED
        c.save(update_fields=["disbursement", "status"])

    logger.info(
        "Generated disbursement #%s to %s for period %s → %s "
        "(premium=%s, commission=%s, net=%s)",
        disbursement.id,
        insurance_company.name,
        period_start,
        period_end,
        total_premium,
        total_commission,
        disbursement.net_amount_payable,
    )
    return disbursement


@transaction.atomic
def mark_disbursement_processed(disbursement: Disbursement, user) -> Disbursement:
    """
    Mark a disbursement as processed (i.e., payment to insurer completed).
    """
    if disbursement.status == DisbursementStatus.PROCESSED:
        raise DisbursementServiceError("This disbursement is already processed.")

    disbursement.status = DisbursementStatus.PROCESSED
    disbursement.processed_by = user
    disbursement.processed_at = timezone.now()
    disbursement.save(update_fields=["status", "processed_by", "processed_at"])

    logger.info(
        "Disbursement #%s marked as PROCESSED by %s",
        disbursement.id,
        getattr(user, "username", "system"),
    )
    return disbursement
