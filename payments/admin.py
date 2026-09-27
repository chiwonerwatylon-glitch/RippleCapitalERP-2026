# payments/admin.py
from django.contrib import admin
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "receipt_number",
        "amount",
        "method",
        "policy_number",
        "client_name",
        "insurer_name",
        "payment_date",
        "received_by",
    )
    list_filter = ("method", "payment_date", "installment__policy__insurance_company")
    search_fields = (
        "receipt_number",
        "reference_number",
        "installment__policy__policy_number",
        "installment__policy__client__full_name",
    )
    readonly_fields = ("payment_date",)

    def policy_number(self, obj):
        return obj.installment.policy.policy_number
    policy_number.short_description = "Policy No."

    def client_name(self, obj):
        return obj.installment.policy.client.full_name
    client_name.short_description = "Client"

    def insurer_name(self, obj):
        return obj.installment.policy.insurance_company.name
    insurer_name.short_description = "Insurer"
