# policies/views.py
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    TemplateView,
)

from .models import Policy, PremiumInstallment
from .forms import PolicyForm, PolicyRenewalForm
from .services import renew_policy
from core.mixins import AdminRequiredMixin, AccountantRequiredMixin, AgentRequiredMixin
from payments.models import Payment


class PolicyListView(LoginRequiredMixin, ListView):
    model = Policy
    template_name = "policies/policy_list.html"
    context_object_name = "policies"
    paginate_by = 25

    def get_queryset(self):
        qs = Policy.objects.select_related(
            "client", "insurance_company", "class_of_business"
        )
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(policy_number__icontains=q) | qs.filter(
                client__full_name__icontains=q
            ) | qs.filter(insurance_company__name__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["query"] = self.request.GET.get("q", "")
        return ctx


class PolicyDetailView(LoginRequiredMixin, DetailView):
    model = Policy
    template_name = "policies/policy_detail.html"
    context_object_name = "policy"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        policy = self.object
        installments = policy.installments.all()
        payments = Payment.objects.filter(installment__policy=policy).select_related(
            "installment"
        )
        total_paid = policy.total_instalments_paid()
        outstanding = policy.outstanding_premium()

        ctx["installments"] = installments
        ctx["payments"] = payments
        ctx["total_paid"] = total_paid
        ctx["outstanding"] = outstanding
        return ctx


class PolicyCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = Policy
    form_class = PolicyForm
    template_name = "policies/policy_form.html"

    def form_valid(self, form):
        messages.success(self.request, "Policy created successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("policies:policy_detail", kwargs={"pk": self.object.pk})


class PolicyUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = Policy
    form_class = PolicyForm
    template_name = "policies/policy_form.html"

    def form_valid(self, form):
        messages.success(self.request, "Policy updated successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("policies:policy_detail", kwargs={"pk": self.object.pk})


class InstallmentScheduleView(LoginRequiredMixin, DetailView):
    model = Policy
    template_name = "policies/installment_schedule.html"
    context_object_name = "policy"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["installments"] = self.object.installments.all()
        return ctx


class PolicyRenewalView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    template_name = "policies/policy_renewal.html"

    def get_object(self):
        return Policy.objects.select_related(
            "client", "insurance_company"
        ).get(pk=self.kwargs["pk"])

    def get(self, request, *args, **kwargs):
        policy = self.get_object()
        form = PolicyRenewalForm(instance=policy)
        return self.render_to_response({"policy": policy, "form": form})

    def post(self, request, *args, **kwargs):
        policy = self.get_object()
        form = PolicyRenewalForm(request.POST, instance=policy)
        if form.is_valid():
            renew_policy(policy, form)
            messages.success(request, "Policy renewed successfully.")
            return reverse_lazy("policies:policy_detail", kwargs={"pk": policy.pk})
        return self.render_to_response({"policy": policy, "form": form})
