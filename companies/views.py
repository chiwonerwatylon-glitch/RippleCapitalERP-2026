# companies/views.py
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
)

from .models import InsuranceCompany, ClassOfBusiness
from .forms import InsuranceCompanyForm, ClassOfBusinessForm
from core.mixins import AdminRequiredMixin  # SUPERADMIN / COMPANY_ADMIN only


class CompanyListView(LoginRequiredMixin, ListView):
    model = InsuranceCompany
    template_name = "companies/company_list.html"
    context_object_name = "companies"
    paginate_by = 25

    def get_queryset(self):
        qs = InsuranceCompany.objects.all()
        search = self.request.GET.get("q")
        if search:
            qs = qs.filter(name__icontains=search) | qs.filter(short_code__icontains=search)
        return qs


class CompanyDetailView(LoginRequiredMixin, DetailView):
    model = InsuranceCompany
    template_name = "companies/company_detail.html"
    context_object_name = "company"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        company = self.object
        from policies.models import Policy

        policies = Policy.objects.filter(insurance_company=company).select_related("client")
        ctx["classes"] = company.classes.all()
        ctx["policies"] = policies
        return ctx


class CompanyCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = InsuranceCompany
    form_class = InsuranceCompanyForm
    template_name = "companies/company_form.html"
    success_url = reverse_lazy("companies:company_list")

    def form_valid(self, form):
        messages.success(self.request, "Insurance company created successfully.")
        return super().form_valid(form)


class CompanyUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = InsuranceCompany
    form_class = InsuranceCompanyForm
    template_name = "companies/company_form.html"
    success_url = reverse_lazy("companies:company_list")

    def form_valid(self, form):
        messages.success(self.request, "Insurance company updated successfully.")
        return super().form_valid(form)


class ClassOfBusinessCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = ClassOfBusiness
    form_class = ClassOfBusinessForm
    template_name = "companies/class_of_business_form.html"

    def get_initial(self):
        initial = super().get_initial()
        company_id = self.request.GET.get("company")
        if company_id:
            initial["insurance_company"] = company_id
        return initial

    def get_success_url(self):
        company = self.object.insurance_company
        messages.success(self.request, "Class of business created successfully.")
        return reverse_lazy("companies:company_detail", kwargs={"pk": company.pk})
