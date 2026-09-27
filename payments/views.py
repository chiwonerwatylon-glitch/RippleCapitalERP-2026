# payments/views.py
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, DetailView

from .models import Payment
from .forms import PaymentForm
from .services import create_payment_from_form
from core.mixins import AdminRequiredMixin  # adjust if agents/accountants can also record payments


class PaymentListView(LoginRequiredMixin, ListView):
    model = Payment
    template_name = "payments/payment_list.html"
    context_object_name = "payments"
    paginate_by = 25

    def get_queryset(self):
        qs = Payment.objects.select_related(
            "installment__policy__client",
            "installment__policy__insurance_company",
            "received_by",
        )
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(
                receipt_number__icontains=q
            ) | qs.filter(
                installment__policy__policy_number__icontains=q
            ) | qs.filter(
                installment__policy__client__full_name__icontains=q
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["query"] = self.request.GET.get("q", "")
        return ctx


class PaymentCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = Payment
    form_class = PaymentForm
    template_name = "payments/payment_form.html"
    success_url = reverse_lazy("payments:payment_list")

    def form_valid(self, form):
        try:
            payment = create_payment_from_form(form, user=self.request.user)
        except Exception as exc:
            messages.error(self.request, f"Could not save payment: {exc}")
            return self.form_invalid(form)

        messages.success(
            self.request,
            f"Payment recorded successfully. Receipt #{payment.receipt_number}",
        )
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("payments:payment_detail", kwargs={"pk": self.object.pk})


class PaymentDetailView(LoginRequiredMixin, DetailView):
    model = Payment
    template_name = "payments/receipt_pdf.html"
    context_object_name = "payment"
