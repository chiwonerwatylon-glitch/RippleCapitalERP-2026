# accounts/permissions.py
from django.core.exceptions import PermissionDenied


def require_admin(user):
    """
    Raise PermissionDenied if user is not SUPERADMIN or COMPANY_ADMIN.
    """
    if not user.is_authenticated or not getattr(user, "is_admin", lambda: False)():
        raise PermissionDenied("You do not have permission to manage users.")
