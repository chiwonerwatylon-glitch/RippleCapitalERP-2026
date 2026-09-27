# reports/services.py
from datetime import date
from decimal import Decimal
from typing import Optional

from django.db.models import Sum, Count, Q

from commissions.models import Commission, CommissionStatus
from payments.models import Payment
from policies.models import Policy, PremiumInstallment
from companies.models import InsuranceCompany


def _in_date_range(qs, start_date: Optional[date], end_date: Optional[date], field_name="created_at"):
    """
    Helper to filter a queryset by date range on the given field.
    """
    if start_date:
        qs = qs.filter(**{f"{field_name}__date__gte": start_date})
    if end_date:
        qs = qs.filter(**{f"{field_name}__date__lte": end_date})
    return qs


def get_dashboard_summary(start_date: Optional[date] = None, end_date: Optional[date] = None) -> dict:
    """
    Overall financial snapshot for the dashboard.
    - total_premium_collected: sum of all payments (liability to insurers)
    - total_commission_earned: sum of all commissions (Ripple Capital revenue)
    - total_outstanding_premium: sum of balances on unpaid installments
    """
    payments_qs = Payment.objects.all()
    commissions_qs = Commission.objects.all()
    installments_qs = PremiumInstallment.objects.exclude(status="PAID")

    payments_qs = _in_date_range(payments_qs, start_date, end_date, field_name="payment_date")
    commissions_qs = _in_date_range(commissions_qs, start_date, end_date, field_name="created_at")
    # Outstanding is point-in-time; you may or may not want date filtering here.
    # For now we don't filter installments by date for outstanding.

    total_premium_collected = payments_qs.aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0.00")

    total_commission_earned = commissions_qs.filter(
        status__in=[CommissionStatus.CONFIRMED, CommissionStatus.SETTLED]
    ).aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0.00")

    total_outstanding_premium = installments_qs.aggregate(
        total=Sum("balance")
    )["total"] or Decimal("0.00")

    return {
        "total_premium_collected": total_premium_collected,
        "total_commission_earned": total_commission_earned,
        "total_outstanding_premium": total_outstanding_premium,
    }


def get_commission_report(start_date: Optional[date] = None, end_date: Optional[date] = None):
    """
    Detailed commission report grouped by insurer.

    Returns queryset of dict rows with:
    - insurance_company__id
    - insurance_company__name
    - total_commission
    - commission_count
    """
    qs = Commission.objects.filter(
        status__in=[CommissionStatus.CONFIRMED, CommissionStatus.SETTLED]
    ).select_related("policy__insurance_company")

    qs = _in_date_range(qs, start_date, end_date, field_name="created_at")

    return (
        qs.values("policy__insurance_company__id", "policy__insurance_company__name")
        .annotate(
            total_commission=Sum("amount"),
            commission_count=Count("id"),
        )
        .order_by("-total_commission")
    )


def get_company_report(insurance_company: InsuranceCompany,
                       start_date: Optional[date] = None,
                       end_date: Optional[date] = None) -> dict:
    """
    Report for a single insurer:
    - total_premium_collected
    - total_commission
    - net_premium_to_insurer
    - policy_count
    - top_clients by premium
    """
    payments_qs = Payment.objects.filter(
        installment__policy__insurance_company=insurance_company
    )
    commissions_qs = Commission.objects.filter(
        policy__insurance_company=insurance_company,
        status__in=[CommissionStatus.CONFIRMED, CommissionStatus.SETTLED],
    )
    policies_qs = Policy.objects.filter(insurance_company=insurance_company)

    payments_qs = _in_date_range(payments_qs, start_date, end_date, field_name="payment_date")
    commissions_qs = _in_date_range(commissions_qs, start_date, end_date, field_name="created_at")
    policies_qs = _in_date_range(policies_qs, start_date, end_date, field_name="created_at")

    total_premium_collected = payments_qs.aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0.00")

    total_commission = commissions_qs.aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0.00")

    policy_count = policies_qs.count()
    net_premium_to_insurer = total_premium_collected - total_commission

    # Top clients by premium volume with this insurer
    top_clients = (
        payments_qs.values(
            "installment__policy__client__id",
            "installment__policy__client__full_name",
        )
        .annotate(total_premium=Sum("amount"))
        .order_by("-total_premium")[:10]
    )

    return {
        "insurance_company": insurance_company,
        "total_premium_collected": total_premium_collected,
        "total_commission": total_commission,
        "net_premium_to_insurer": net_premium_to_insurer,
        "policy_count": policy_count,
        "top_clients": top_clients,
    }


def get_outstanding_premium_report():
    """
    Outstanding premium aging report.

    Groups unpaid installment balances by age buckets:
    - current (due date >= today)
    - 0–30 days overdue
    - 31–60 days
    - 61–90 days
    - 90+ days

    Returns a dict with totals per bucket.
    """
    today = date.today()
    qs = PremiumInstallment.objects.exclude(status="PAID").values(
        "due_date", "balance",
    )

    def bucket(inst):
        due = inst["due_date"]
        bal = inst["balance"] or Decimal("0.00")
        delta = (today - due).days
        if delta <= 0:
            return "current", bal
        elif delta <= 30:
            return "overdue_0_30", bal
        elif delta <= 60:
            return "overdue_31_60", bal
        elif delta <= 90:
            return "overdue_61_90", bal
        else:
            return "overdue_90_plus", bal

    totals = {
        "current": Decimal("0.00"),
        "overdue_0_30": Decimal("0.00"),
        "overdue_31_60": Decimal("0.00"),
        "overdue_61_90": Decimal("0.00"),
        "overdue_90_plus": Decimal("0.00"),
    }

    for inst in qs:
        key, bal = bucket(inst)
        totals[key] += bal

    return totals
