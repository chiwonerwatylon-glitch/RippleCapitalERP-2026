from flask import flash, redirect, url_for
from flask_login import current_user
from functools import wraps
from .models import User, ROLE_ADMIN, ROLE_OWNER, ROLE_AGENT, ROLE_CLIENT


def get_account_owner_id(user=None):
    """Return the id of the account owner whose data the user works with.

    Owners are the account owner of their own data. Admin and agent users
    belong to the primary (earliest registered, active) owner's account, so
    every staff member reads and writes the same shared data set via owner_id.
    Returns None when there is no authenticated user.
    """
    user = user or current_user
    if not user or not getattr(user, "is_authenticated", False):
        return None

    if user.role == ROLE_OWNER:
        return user.id

    primary_owner = (
        User.query.filter_by(role=ROLE_OWNER, is_active=True)
        .order_by(User.id)
        .first()
    )
    return primary_owner.id if primary_owner else user.id


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login"))

            if current_user.role not in roles:
                flash("You do not have permission to access this page.", "danger")
                return redirect(url_for("core.index"))
            return view_func(*args, **kwargs)
        return wrapped_view
    return decorator

