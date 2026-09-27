# core/templatetags/custom_filters.py
from django import template
from django.utils.html import format_html

register = template.Library()


@register.filter
def currency(value, symbol="KES"):
    """
    Format a Decimal or number as currency with thousands separator.
    Usage: {{ amount|currency }}  -> KES 10,000.00
    """
    try:
        return f"{symbol} {float(value):,.2f}"
    except (TypeError, ValueError):
        return f"{symbol} 0.00"


@register.filter
def commission_status_badge(status):
    """
    Render a Bootstrap-style badge for a commission status.
    Usage: {{ commission.status|commission_status_badge|safe }}
    """
    if status == "PENDING":
        cls = "bg-warning text-dark"
        label = "Pending"
    elif status == "CONFIRMED":
        cls = "bg-success"
        label = "Confirmed"
    elif status == "REVERSED":
        cls = "bg-danger"
        label = "Reversed"
    elif status == "SETTLED":
        cls = "bg-primary"
        label = "Settled"
    else:
        cls = "bg-secondary"
        label = status

    return format_html('<span class="badge {}">{}</span>', cls, label)


@register.filter
def short_date(value):
    """
    Format a date or datetime as YYYY-MM-DD.
    Usage: {{ obj.created_at|short_date }}
    """
    if not value:
        return ""
    return value.strftime("%Y-%m-%d")
