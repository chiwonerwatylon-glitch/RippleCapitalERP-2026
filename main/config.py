import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(basedir, "app.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    REMEMBER_COOKIE_DURATION = timedelta(days=7)
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")  # used for real email sending
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    DEFAULT_SENDER = os.environ.get("DEFAULT_SENDER", "noreply@ripplecapitalfinance.co.zw")
    MAIL_FROM = os.environ.get("MAIL_FROM", "noreply@ripplecapitalfinance.co.zw")
    RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
    PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "")
    SCHEDULER_TIMEZONE = "UTC"

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

config_by_name = {
    "dev": DevelopmentConfig,
    "prod": ProductionConfig,
    "default": DevelopmentConfig,
}
