# policies/admin.py
from django.contrib import admin
from .models import Policy, PremiumInstallment


class PremiumInstallmentInline(admin.TabularInline):
    model = PremiumInstallment
    extra = 0
    readonly_fields = ("amount_paid", "balance", "status")


@admin.register(Policy)
class PolicyAdmin(admin.ModelAdmin):
    list_display = (
        "policy_number",
        "client",
        "insurance_company",
        "class_of_business",
        "premium_amount",
        "commission_rate",
        "start_date",
        "end_date",
        "status",
    )
    list_filter = ("insurance_company", "class_of_business", "status", "start_date")
    search_fields = ("policy_number", "client__full_name")
    inlines = [PremiumInstallmentInline]
    readonly_fields = ("created_at",)


@admin.register(PremiumInstallment)
class PremiumInstallmentAdmin(admin.ModelAdmin):
    list_display = (
        "policy",
        "installment_number",
        "due_date",
        "amount_due",
        "amount_paid",
        "balance",
        "status",
    )
    list_filter = ("status", "due_date", "policy__insurance_company")
    search_fields = ("policy__policy_number",)
