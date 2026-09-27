# disbursements/views.py
from datetime import date

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, View

from .models import Disbursement
from .forms import DisbursementFilterForm, GenerateDisbursementForm
from .services import generate_disbursement, mark_disbursement_processed, DisbursementServiceError
from core.mixins import AdminRequiredMixin  # SUPERADMIN / COMPANY_ADMIN


class DisbursementListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    model = Disbursement
    template_name = "disbursements/disbursement_list.html"
    context_object_name = "disbursements"
    paginate_by = 25

    def get_queryset(self):
        qs = Disbursement.objects.select_related("insurance_company")
        form = DisbursementFilterForm(self.request.GET or None)
        self.filter_form = form
        if form.is_valid():
            insurer = form.cleaned_data.get("insurance_company")
            status = form.cleaned_data.get("status")
            if insurer:
                qs = qs.filter(insurance_company=insurer)
            if status:
                qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["filter_form"] = getattr(self, "filter_form", DisbursementFilterForm())
        return ctx


class DisbursementDetailView(LoginRequiredMixin, AdminRequiredMixin, DetailView):
    model = Disbursement
    template_name = "disbursements/disbursement_detail.html"
    context_object_name = "disbursement"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        disb = self.object
        ctx["commissions"] = disb.commission_items.select_related(
            "policy", "policy__client"
        ).order_by("policy__policy_number")
        return ctx


class GenerateDisbursementView(LoginRequiredMixin, AdminRequiredMixin, View):
    template_name = "disbursements/disbursement_list.html"  # will redirect after

    def get(self, request, *args, **kwargs):
        form = GenerateDisbursementForm()
        return render(request, "disbursements/disbursement_generate.html", {"form": form})

    def post(self, request, *args, **kwargs):
        form = GenerateDisbursementForm(request.POST)
        if form.is_valid():
            ic = form.cleaned_data["insurance_company"]
            start = form.cleaned_data["period_start"]
            end = form.cleaned_data["period_end"]
            try:
                disb = generate_disbursement(ic, start, end, request.user)
                messages.success(
                    request,
                    f"Disbursement #{disb.id} generated for {ic.name} covering {start} → {end}.",
                )
                return redirect("disbursements:disbursement_detail", pk=disb.pk)
            except DisbursementServiceError as exc:
                messages.error(request, str(exc))
        return render(request, "disbursements/disbursement_generate.html", {"form": form})


class DisbursementMarkProcessedView(LoginRequiredMixin, AdminRequiredMixin, View):
    def post(self, request, pk):
        disb = get_object_or_404(Disbursement, pk=pk)
        try:
            mark_disbursement_processed(disb, request.user)
            messages.success(request, "Disbursement marked as processed.")
        except DisbursementServiceError as exc:
            messages.error(request, str(exc))
        return redirect("disbursements:disbursement_detail", pk=pk)


class DisbursementVoucherView(LoginRequiredMixin, AdminRequiredMixin, DetailView):
    """
    Renders a voucher-style page that can be printed to PDF.
    Hook this template into a PDF generator externally.
    """
    model = Disbursement
    template_name = "disbursements/disbursement_voucher_pdf.html"
    context_object_name = "disbursement"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        disb = self.object
        ctx["commissions"] = disb.commission_items.select_related(
            "policy", "policy__client"
        ).order_by("policy__policy_number")
        return ctx
