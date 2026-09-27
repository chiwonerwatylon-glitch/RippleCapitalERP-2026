# clients/filters.py
from django.db.models import Q
from .models import Client


def filter_clients(queryset, query: str | None):
    """
    Simple text search for client list:
    search by name, id_number, tax_pin, email, phone.
    """
    if not query:
        return queryset
    q = query.strip()
    return queryset.filter(
        Q(full_name__icontains=q)
        | Q(id_number__icontains=q)
        | Q(tax_pin__icontains=q)
        | Q(email__icontains=q)
        | Q(phone_number__icontains=q)
    )
