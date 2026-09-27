# disbursements/forms.py
from django import forms
from .models import Disbursement


class DisbursementFilterForm(forms.Form):
    insurance_company = forms.ModelChoiceField(
        queryset=None,
        required=False,
        label="Insurer",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    status = forms.ChoiceField(
        choices=[("", "All")] + list(Disbursement._meta.get_field("status").choices),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, **kwargs):
        from companies.models import InsuranceCompany
        super().__init__(*args, **kwargs)
        self.fields["insurance_company"].queryset = InsuranceCompany.objects.all()


class GenerateDisbursementForm(forms.Form):
    insurance_company = forms.ModelChoiceField(
        queryset=None,
        label="Insurance company",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    period_start = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    period_end = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        from companies.models import InsuranceCompany
        super().__init__(*args, **kwargs)
        self.fields["insurance_company"].queryset = InsuranceCompany.objects.filter(is_active=True)

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("period_start")
        end = cleaned.get("period_end")
        if start and end and end < start:
            self.add_error("period_end", "End date cannot be before start date.")
        return cleaned
