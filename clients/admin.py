# clients/admin.py
from django.contrib import admin
from .models import Client


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("full_name", "client_type", "phone_number", "email", "created_at")
    list_filter = ("client_type", "created_at")
    search_fields = ("full_name", "id_number", "tax_pin", "email", "phone_number")
    readonly_fields = ("created_at", "created_by")

    def save_model(self, request, obj, form, change):
        if not change and not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
