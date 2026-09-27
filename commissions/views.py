"""
commissions/views.py

Read-only views for commissions and agent payouts.
"""

from datetime import date

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView, TemplateView
from django.utils import timezone

from .models import Commission, AgentCommissionPayout
from . import services


class AdminOrAccountantRequiredMixin(UserPassesTestMixin):
    """
    Only allow Super Admins / Company Admins / Accountants to see
    global commission data. Adjust this to your actual role logic.
    """

    def test_func(self):
        user = self.request.user
        # Assuming Role enum: SUPERADMIN, COMPANY_ADMIN, ACCOUNTANT, AGENT, VIEWER
        return getattr(user, "role", None) in ("SUPERADMIN", "COMPANY_ADMIN", "ACCOUNTANT")


class CommissionListView(LoginRequiredMixin, AdminOrAccountantRequiredMixin, ListView):
    model = Commission
    template_name = "commissions/commission_list.html"
    context_object_name = "commissions"
    paginate_by = 25

    def get_queryset(self):
        qs = Commission.objects.all()

        insurer_id = self.request.GET.get("insurer")
        status = self.request.GET.get("status")
        start = self.request.GET.get("start")
        end = self.request.GET.get("end")

        if insurer_id:
            qs = qs.filter(policy__insurance_company_id=insurer_id)
        if status:
            qs = qs.filter(status=status)
        if start and end:
            qs = qs.for_period(start, end)

        return qs


class CommissionDetailView(LoginRequiredMixin, AdminOrAccountantRequiredMixin, DetailView):
    model = Commission
    template_name = "commissions/commission_detail.html"
    context_object_name = "commission"


class CommissionSummaryView(LoginRequiredMixin, AdminOrAccountantRequiredMixin, TemplateView):
    template_name = "commissions/commission_summary.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        start_str = self.request.GET.get("start")
        end_str = self.request.GET.get("end")
        insurer_id = self.request.GET.get("insurer")

        start_date = date.fromisoformat(start_str) if start_str else None
        end_date = date.fromisoformat(end_str) if end_str else None
        insurer = None
        if insurer_id:
            from companies.models import InsuranceCompany
            insurer = InsuranceCompany.objects.filter(pk=insurer_id).first()

        summary = services.get_commission_summary(
            start_date=start_date,
            end_date=end_date,
            insurance_company=insurer,
        )

        ctx["summary"] = summary
        ctx["start_date"] = start_date
        ctx["end_date"] = end_date
        ctx["insurer"] = insurer
        ctx["by_insurer"] = services.get_commission_breakdown_by_insurer(start_date, end_date)
        ctx["by_agent"] = services.get_commission_breakdown_by_agent(start_date, end_date)
        return ctx


class AgentPayoutListView(LoginRequiredMixin, AdminOrAccountantRequiredMixin, ListView):
    model = AgentCommissionPayout
    template_name = "commissions/payout_list.html"
    context_object_name = "payouts"
    paginate_by = 25

    def get_queryset(self):
        qs = AgentCommissionPayout.objects.select_related("agent", "paid_by")
        agent_id = self.request.GET.get("agent")
        if agent_id:
            qs = qs.filter(agent_id=agent_id)
        return qs
