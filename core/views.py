# core/views.py
from datetime import date

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.generic import TemplateView

from .mixins import AdminRequiredMixin, AccountantRequiredMixin, AgentRequiredMixin
from core.utils import current_month_range

from commissions.models import Commission, CommissionStatus
from commissions import services as commission_services
from payments.models import Payment
from policies.models import Policy


@login_required
def dashboard_router(request):
    """
    Redirects a logged-in user to the correct dashboard based on role.
    """
    user = request.user
    role = getattr(user, "role", None)

    if role in ("SUPERADMIN", "COMPANY_ADMIN"):
        return redirect("core:dashboard-admin")
    elif role == "ACCOUNTANT":
        return redirect("core:dashboard-accountant")
    elif role == "AGENT":
        return redirect("core:dashboard-agent")

    # Fallback: no specific role → treat like read-only user
    return redirect("core:dashboard-accountant")


class AdminDashboardView(AdminRequiredMixin, TemplateView):
    """
    High-level view for Ripple Capital leadership:
    - Total commissions (company revenue)
    - Per-insurer summary
    - Recent payments & policies
    """
    template_name = "core/dashboard_admin.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        start, end = current_month_range()
        summary = commission_services.get_commission_summary(start_date=start, end_date=end)

        ctx["summary"] = summary
        ctx["month_start"] = start
        ctx["month_end"] = end
        ctx["by_insurer"] = commission_services.get_commission_breakdown_by_insurer(start, end)[:10]
        ctx["recent_policies"] = Policy.objects.select_related(
            "client", "insurance_company"
        ).order_by("-created_at")[:5]
        ctx["recent_payments"] = Payment.objects.select_related(
            "installment__policy__client",
            "installment__policy__insurance_company",
        ).order_by("-payment_date")[:5]
        return ctx


class AccountantDashboardView(AccountantRequiredMixin, TemplateView):
    """
    Focused on:
    - Pending commissions to review
    - Outstanding commissions not yet settled to insurers
    - Recent payments
    """
    template_name = "core/dashboard_accountant.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = date.today()
        start, end = current_month_range()

        summary = commission_services.get_commission_summary()
        ctx["summary"] = summary
        ctx["today"] = today

        ctx["pending_commissions"] = Commission.objects.pending().order_by("-created_at")[:10]
        ctx["unsettled_commissions"] = (
            Commission.objects.confirmed().undisbursed().order_by("-created_at")[:10]
        )
        ctx["recent_payments"] = Payment.objects.select_related(
            "installment__policy__client",
            "installment__policy__insurance_company",
        ).order_by("-payment_date")[:10]

        return ctx


class AgentDashboardView(AgentRequiredMixin, TemplateView):
    """
    For internal staff with role AGENT:
    - Policies they handled
    - Commissions generated from their policies (REMINDER: revenue still belongs to Ripple Capital)
    """
    template_name = "core/dashboard_agent.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        start, end = current_month_range()

        commissions_qs = Commission.objects.confirmed().for_agent(user).for_period(start, end)
        ctx["total_commission_this_month"] = commissions_qs.total_amount()
        ctx["commission_count_this_month"] = commissions_qs.count()

        ctx["recent_commissions"] = commissions_qs.order_by("-created_at")[:10]
        ctx["recent_policies"] = Policy.objects.filter(agent=user).select_related(
            "client", "insurance_company"
        ).order_by("-created_at")[:5]

        return ctx


@login_required
def permission_denied_view(request, exception=None):
    """
    Simple 403 page for unauthorized access attempts.
    """
    return render(request, "core/permission_denied.html", status=403)

