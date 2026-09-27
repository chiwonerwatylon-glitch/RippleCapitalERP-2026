# core/urls.py
from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("", views.dashboard_router, name="dashboard-home"),
    path("admin/", views.AdminDashboardView.as_view(), name="dashboard-admin"),
    path("accountant/", views.AccountantDashboardView.as_view(), name="dashboard-accountant"),
    path("agent/", views.AgentDashboardView.as_view(), name="dashboard-agent"),
    path("permission-denied/", views.permission_denied_view, name="permission-denied"),
]
