# policies/forms.py
from django import forms
from .models import Policy


class PolicyForm(forms.ModelForm):
    class Meta:
        model = Policy
        fields = [
            "policy_number",
            "client",
            "insurance_company",
            "class_of_business",
            "sum_insured",
            "premium_amount",
            "commission_rate",
            "start_date",
            "end_date",
            "status",
            "agent",
        ]
        widgets = {
            "policy_number": forms.TextInput(attrs={"class": "form-control"}),
            "client": forms.Select(attrs={"class": "form-select"}),
            "insurance_company": forms.Select(attrs={"class": "form-select"}),
            "class_of_business": forms.Select(attrs={"class": "form-select"}),
            "sum_insured": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "premium_amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "commission_rate": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "start_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "end_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "agent": forms.Select(attrs={"class": "form-select"}),
        }


class PolicyRenewalForm(forms.ModelForm):
    """
    Simple renewal form: allow editing new premium, sum insured and dates.
    """
    class Meta:
        model = Policy
        fields = [
            "sum_insured",
            "premium_amount",
            "commission_rate",
            "start_date",
            "end_date",
        ]
        widgets = {
            "sum_insured": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "premium_amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "commission_rate": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "start_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "end_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        }
