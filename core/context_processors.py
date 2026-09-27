# core/context_processors.py
from django.utils import timezone


def branding(request):
    """
    Inject basic branding info into all templates.
    """
    return {
        "BRAND_NAME": "Ripple Capital Private Limited",
        "BRAND_SHORT": "Ripple Capital",
        "CURRENT_YEAR": timezone.now().year,
    }
