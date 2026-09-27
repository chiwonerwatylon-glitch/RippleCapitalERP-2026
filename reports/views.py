# reports/views.py
from datetime import date

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.shortcuts import get_object_or_404

from core.mixins import AdminRequiredMixin, AccountantRequiredMixin
from companies.models import InsuranceCompany
from .forms import DateRangeForm, CompanyReportFilterForm
from . import services


class ReportsDashboardView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    """
    High-level reporting dashboard for Ripple Capital leadership.
    """
    template_name = "reports/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        form = DateRangeForm(self.request.GET or None)

        start_date = end_date = None
        if form.is_valid():
            start_date = form.cleaned_data.get("start_date")
            end_date = form.cleaned_data.get("end_date")

        summary = services.get_dashboard_summary(start_date, end_date)
        commission_by_insurer = services.get_commission_report(start_date, end_date)[:10]

        ctx["form"] = form
        ctx["summary"] = summary
        ctx["commission_by_insurer"] = commission_by_insurer
        return ctx


class CommissionReportView(LoginRequiredMixin, AccountantRequiredMixin, TemplateView):
    """
    Detailed commission report grouped by insurer.
    """
    template_name = "reports/commission_report.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        form = DateRangeForm(self.request.GET or None)
        start_date = end_date = None
        if form.is_valid():
            start_date = form.cleaned_data.get("start_date")
            end_date = form.cleaned_data.get("end_date")

        rows = services.get_commission_report(start_date, end_date)
        ctx["form"] = form
        ctx["rows"] = rows
        return ctx


class CompanyReportView(LoginRequiredMixin, AccountantRequiredMixin, TemplateView):
    """
    Report for a single insurer (underwriter).
    """
    template_name = "reports/company_report.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        form = CompanyReportFilterForm(self.request.GET or None)

        if not form.is_valid() or not form.cleaned_data.get("insurance_company"):
            # If no company selected, just show the form
            ctx["form"] = form
            ctx["report"] = None
            return ctx

        company = form.cleaned_data["insurance_company"]
        start_date = form.cleaned_data.get("start_date")
        end_date = form.cleaned_data.get("end_date")

        report = services.get_company_report(company, start_date, end_date)

        ctx["form"] = form
        ctx["report"] = report
        return ctx


class OutstandingPremiumReportView(LoginRequiredMixin, AccountantRequiredMixin, TemplateView):
    """
    Aging report for outstanding premium (liability to insurers).
    """
    template_name = "reports/outstanding_report.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        totals = services.get_outstanding_premium_report()
        ctx["totals"] = totals
        ctx["today"] = date.today()
        return ctx
