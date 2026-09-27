# payments/forms.py
from django import forms
from .models import Payment, PaymentMethod
from .utils import generate_receipt_number
from policies.models import PremiumInstallment


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = [
            "installment",
            "amount",
            "method",
            "reference_number",
        ]
        widgets = {
            "installment": forms.Select(attrs={"class": "form-select"}),
            "amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "method": forms.Select(attrs={"class": "form-select"}),
            "reference_number": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        # optionally filter installment choices to unpaid ones
        super().__init__(*args, **kwargs)
        self.fields["installment"].queryset = PremiumInstallment.objects.exclude(status="PAID")

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount <= 0:
            raise forms.ValidationError("Amount must be greater than zero.")
        return amount

    def save(self, commit=True):
        payment = super().save(commit=False)
        if not payment.receipt_number:
            payment.receipt_number = generate_receipt_number()
        return super().save(commit=commit)
