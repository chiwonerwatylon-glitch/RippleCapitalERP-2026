# accounts/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    """
    Internal roles in the Ripple Capital ERP.

    SUPERADMIN   - Full control over system, including settings, users.
    COMPANY_ADMIN- Manages day-to-day operations & users.
    ACCOUNTANT   - Handles financial tasks: commissions, disbursements.
    AGENT        - Staff member who handles policies/clients (still Ripple staff).
    VIEWER       - Read-only access for auditors, managers, etc.
    """
    SUPERADMIN = "SUPERADMIN", "Super Admin"
    COMPANY_ADMIN = "COMPANY_ADMIN", "Company Admin"
    ACCOUNTANT = "ACCOUNTANT", "Accountant"
    AGENT = "AGENT", "Agent"
    VIEWER = "VIEWER", "Viewer"


class User(AbstractUser):
    """
    Custom user model for Ripple Capital ERP.

    Extends Django's AbstractUser and adds:
    - role
    - phone_number
    - is_active_staff (for soft deactivation while keeping record history)
    """
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.AGENT,
        help_text="Internal role for this user in the ERP.",
    )
    phone_number = models.CharField(max_length=20, blank=True)
    is_active_staff = models.BooleanField(
        default=True,
        help_text="If unchecked, user cannot log in but record is preserved.",
    )

    def is_admin(self) -> bool:
        return self.role in {Role.SUPERADMIN, Role.COMPANY_ADMIN}

    def is_accountant(self) -> bool:
        return self.role == Role.ACCOUNTANT

    def is_agent(self) -> bool:
        return self.role == Role.AGENT

    def __str__(self):
        return self.get_full_name() or self.username

