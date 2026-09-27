# accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User, Role


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """
    Admin interface for managing users.
    """

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "email", "phone_number")}),
        ("Role & Status", {"fields": ("role", "is_active_staff", "is_active", "is_staff", "is_superuser")}),
        ("Permissions", {"fields": ("groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "password1", "password2", "role", "is_active_staff"),
        }),
    )

    list_display = ("username", "full_name", "email", "role", "is_active_staff", "is_active")
    list_filter = ("role", "is_active_staff", "is_active", "is_staff")
    search_fields = ("username", "first_name", "last_name", "email")
    ordering = ("username",)

    def full_name(self, obj):
        return obj.get_full_name()
    full_name.short_description = "Full name"
