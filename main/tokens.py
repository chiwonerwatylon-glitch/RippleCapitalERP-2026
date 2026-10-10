"""Signed, expiring, single-use password reset tokens."""
from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .models import User

RESET_SALT = "password-reset"
RESET_MAX_AGE_SECONDS = 3600


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=RESET_SALT)


def _hash_marker(user: User) -> str:
    # Changing the password changes the hash, so a token is invalid once used.
    return user.password_hash[-20:]


def make_reset_token(user: User) -> str:
    return _serializer().dumps({"uid": user.id, "h": _hash_marker(user)})


def verify_reset_token(token: str):
    """Return the user for a valid, unexpired, unused token; otherwise None."""
    try:
        data = _serializer().loads(token, max_age=RESET_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None
    uid = data.get("uid")
    if uid is None:
        return None
    user = User.query.get(uid)
    if not user or not user.is_active:
        return None
    if data.get("h") != _hash_marker(user):
        return None
    return user

