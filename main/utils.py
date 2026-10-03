from flask import flash, redirect, url_for
from flask_login import current_user
from functools import wraps
from .models import ROLE_ADMIN, ROLE_OWNER, ROLE_CLIENT


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

