# insurance_erp/urls.py
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),

    # Auth & user management
    path("", RedirectView.as_view(pattern_name="accounts:login", permanent=False)),
    path("", include("accounts.urls")),

    # Dashboards
    path("dashboard/", include("core.urls")),

    # Domain apps
    path("companies/", include("companies.urls")),
    path("clients/", include("clients.urls")),
    path("policies/", include("policies.urls")),
    path("payments/", include("payments.urls")),
    path("commissions/", include("commissions.urls")),
    path("disbursements/", include("disbursements.urls")),
    path("notifications/", include("notifications.urls", namespace="notifications") if hasattr(__import__('notifications'), 'urls') else []),
    path("reports/", include("reports.urls") if hasattr(__import__('reports'), 'urls') else []),
]

# Custom 403 handler (permission denied)
handler403 = "core.views.permission_denied_view"
