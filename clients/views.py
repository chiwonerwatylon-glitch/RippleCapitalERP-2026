# clients/views.py
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView

from .models import Client
from .forms import ClientForm
from .filters import filter_clients
from core.mixins import AdminRequiredMixin  # SUPERADMIN/COMPANY_ADMIN


class ClientListView(LoginRequiredMixin, ListView):
    model = Client
    template_name = "clients/client_list.html"
    context_object_name = "clients"
    paginate_by = 25

    def get_queryset(self):
        qs = Client.objects.all()
        query = self.request.GET.get("q")
        qs = filter_clients(qs, query)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["query"] = self.request.GET.get("q", "")
        return ctx


class ClientDetailView(LoginRequiredMixin, DetailView):
    model = Client
    template_name = "clients/client_detail.html"
    context_object_name = "client_obj"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        client = self.object

        from policies.models import Policy
        from payments.models import Payment
        from policies.models import PremiumInstallment

        policies = Policy.objects.filter(client=client).select_related("insurance_company")
        payments = Payment.objects.filter(installment__policy__client=client).select_related(
            "installment__policy__insurance_company"
        ).order_by("-payment_date")[:50]

        installments = PremiumInstallment.objects.filter(policy__client=client)

        ctx["policies"] = policies
        ctx["payments"] = payments
        ctx["total_outstanding"] = client.total_outstanding()
        ctx["total_paid"] = client.total_premium_paid()
        ctx["installments"] = installments
        return ctx


class ClientCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = Client
    form_class = ClientForm
    template_name = "clients/client_form.html"
    success_url = reverse_lazy("clients:client_list")

    def form_valid(self, form):
        client = form.save(commit=False)
        client.created_by = self.request.user
        client.save()
        messages.success(self.request, "Client created successfully.")
        return super().form_valid(form)


class ClientUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = Client
    form_class = ClientForm
    template_name = "clients/client_form.html"
    success_url = reverse_lazy("clients:client_list")

    def form_valid(self, form):
        messages.success(self.request, "Client updated successfully.")
        return super().form_valid(form)


class ClientStatementView(LoginRequiredMixin, DetailView):
    """
    Shows a simple statement for a client: policies, payments, outstanding.
    """
    model = Client
    template_name = "clients/client_statement.html"
    context_object_name = "client_obj"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        client = self.object

        from policies.models import PremiumInstallment
        from payments.models import Payment

        installments = PremiumInstallment.objects.filter(policy__client=client).order_by("due_date")
        payments = Payment.objects.filter(installment__policy__client=client).order_by("payment_date")

        ctx["installments"] = installments
        ctx["payments"] = payments
        ctx["total_outstanding"] = client.total_outstanding()
        ctx["total_paid"] = client.total_premium_paid()
        return ctx
