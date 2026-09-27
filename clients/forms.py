# clients/forms.py
from django import forms
from .models import Client, ClientType


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = [
            "client_type",
            "full_name",
            "id_number",
            "tax_pin",
            "email",
            "phone_number",
            "address",
        ]
        widgets = {
            "client_type": forms.Select(attrs={"class": "form-select"}),
            "full_name": forms.TextInput(attrs={"class": "form-control"}),
            "id_number": forms.TextInput(attrs={"class": "form-control"}),
            "tax_pin": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "phone_number": forms.TextInput(attrs={"class": "form-control"}),
            "address": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }
