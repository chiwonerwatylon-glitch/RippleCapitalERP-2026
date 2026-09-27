"""
Django settings for insurance_erp project.

Aligned with Ripple Capital's ERP:
- Custom User in accounts.User
- Apps: accounts, core, companies, clients, policies, payments, commissions, disbursements, notifications, reports
- Templates in BASE_DIR / "templates"
- Static in BASE_DIR / "static"
"""

from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: change this in production!
SECRET_KEY = "replace-this-with-a-secure-random-key"

DEBUG = True

ALLOWED_HOSTS: list[str] = ["*"]

# ----------------------------------------------------------------------
# Applications
# ----------------------------------------------------------------------
INSTALLED_APPS = [
    # Django core
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Project apps
    "accounts",
    "core",
    "companies",
    "clients",
    "policies",
    "payments",
    "commissions",
    "disbursements",
    "notifications",
    "reports",
]

# ----------------------------------------------------------------------
# Middleware
# ----------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "insurance_erp.urls"

# ----------------------------------------------------------------------
# Templates
# ----------------------------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],  # global templates
        "APP_DIRS": True,                  # also search app/templates
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.branding",  # BRAND_NAME, etc.
            ],
        },
    },
]

WSGI_APPLICATION = "insurance_erp.wsgi.application"
ASGI_APPLICATION = "insurance_erp.asgi.application"

# ----------------------------------------------------------------------
# Database (SQLite for dev – switch to PostgreSQL for production)
# ----------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Example PostgreSQL (uncomment & configure for production)
# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.postgresql",
#         "NAME": "ripple_erp",
#         "USER": "postgres",
#         "PASSWORD": "password",
#         "HOST": "localhost",
#         "PORT": "5432",
#     }
# }

# ----------------------------------------------------------------------
# Auth
# ----------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    # You can enable these gradually
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    # {
    #     "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    # },
    # {
    #     "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    # },
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:dashboard-home"
LOGOUT_REDIRECT_URL = "accounts:login"

# ----------------------------------------------------------------------
# Internationalization
# ----------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Nairobi"
USE_I18N = True
USE_TZ = True

# ----------------------------------------------------------------------
# Static & Media
# ----------------------------------------------------------------------
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ----------------------------------------------------------------------
# Email (console backend for development)
# ----------------------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "Ripple Capital ERP <noreply@ripplecapital.com>"

# For production, switch to SMTP, e.g.:
# EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
# EMAIL_HOST = "smtp.gmail.com"
# EMAIL_PORT = 587
# EMAIL_USE_TLS = True
# EMAIL_HOST_USER = "your-email@gmail.com"
# EMAIL_HOST_PASSWORD = "your-app-password"
# DEFAULT_FROM_EMAIL = "Ripple Capital ERP <noreply@ripplecapital.com>"

# ----------------------------------------------------------------------
# Celery (basic settings – adjust broker/backend in production)
# ----------------------------------------------------------------------
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60

# Example periodic task (hook notifications here later)
CELERY_BEAT_SCHEDULE = {
    # "daily-premium-reminders": {
    #     "task": "notifications.tasks.send_premium_due_reminders",
    #     "schedule": 86400.0,  # every 24 hours
    # },
}

# ----------------------------------------------------------------------
# Security (adjust for production)
# ----------------------------------------------------------------------
# CSRF_COOKIE_SECURE = True
# SESSION_COOKIE_SECURE = True
# SECURE_HSTS_SECONDS = 31536000
# SECURE_HSTS_INCLUDE_SUBDOMAINS = True
# SECURE_HSTS_PRELOAD = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
