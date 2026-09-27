# companies/forms.py
from django import forms
from .models import InsuranceCompany, ClassOfBusiness


class InsuranceCompanyForm(forms.ModelForm):
    class Meta:
        model = InsuranceCompany
        fields = [
            "name",
            "short_code",
            "contact_email",
            "contact_phone",
            "address",
            "bank_account_details",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "short_code": forms.TextInput(attrs={"class": "form-control"}),
            "contact_email": forms.EmailInput(attrs={"class": "form-control"}),
            "contact_phone": forms.TextInput(attrs={"class": "form-control"}),
            "address": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "bank_account_details": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class ClassOfBusinessForm(forms.ModelForm):
    class Meta:
        model = ClassOfBusiness
        fields = [
            "insurance_company",
            "name",
            "default_commission_rate",
        ]
        widgets = {
            "insurance_company": forms.Select(attrs={"class": "form-select"}),
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "default_commission_rate": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
        }
