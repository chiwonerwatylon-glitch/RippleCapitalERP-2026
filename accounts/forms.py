# accounts/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm, AuthenticationForm

from .models import User, Role


class RippleLoginForm(AuthenticationForm):
    """
    Used by your custom login page (registration/login.html).
    """
    username = forms.CharField(
        label="User ID",
        widget=forms.TextInput(attrs={
            "id": "id_username",
            "placeholder": "Enter your user ID",
            "autocomplete": "username",
            "autocapitalize": "none",
            "autocorrect": "off",
            "spellcheck": "false",
            "tabindex": "1",
        })
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={
            "id": "id_password",
            "placeholder": "Enter your password",
            "autocomplete": "current-password",
            "autocapitalize": "none",
            "autocorrect": "off",
            "spellcheck": "false",
            "tabindex": "2",
        })
    )
    remember_me = forms.BooleanField(required=False, label="Remember me")


class UserCreateForm(UserCreationForm):
    """
    Form for creating new ERP users (by admin).
    """
    class Meta:
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "role",
            "is_active_staff",
        )


class UserUpdateForm(UserChangeForm):
    """
    Form for updating existing ERP users (by admin).
    Password is not editable here; use password reset/change flows.
    """
    password = None  # hide password field from this form

    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "role",
            "is_active_staff",
            "is_active",
        )
