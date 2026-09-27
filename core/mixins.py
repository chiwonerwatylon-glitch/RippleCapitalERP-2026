# core/mixins.py
from django.contrib.auth.mixins import UserPassesTestMixin


class RoleRequiredMixin(UserPassesTestMixin):
    """
    Base mixin to restrict access to users with specific roles.
    Subclasses must define allowed_roles = ("ROLE1", "ROLE2", ...)
    """

    allowed_roles: tuple[str, ...] = ()

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        if not self.allowed_roles:
            return True
        return getattr(user, "role", None) in self.allowed_roles


class AdminRequiredMixin(RoleRequiredMixin):
    """
    For SUPERADMIN / COMPANY_ADMIN users.
    """
    allowed_roles = ("SUPERADMIN", "COMPANY_ADMIN")


class AccountantRequiredMixin(RoleRequiredMixin):
    """
    For ACCOUNTANT users.
    """
    allowed_roles = ("ACCOUNTANT",)


class AgentRequiredMixin(RoleRequiredMixin):
    """
    For internal staff marked as AGENT role.
    Remember: Ripple Capital itself is the broker; this is just user type.
    """
    allowed_roles = ("AGENT",)
