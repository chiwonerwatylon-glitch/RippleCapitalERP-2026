# reports/urls.py
from django.urls import path
from .views import (
    ReportsDashboardView,
    CommissionReportView,
    CompanyReportView,
    OutstandingPremiumReportView,
)

app_name = "reports"

urlpatterns = [
    path("", ReportsDashboardView.as_view(), name="dashboard"),
    path("commissions/", CommissionReportView.as_view(), name="commission_report"),
    path("company/", CompanyReportView.as_view(), name="company_report"),
    path("outstanding/", OutstandingPremiumReportView.as_view(), name="outstanding_report"),
]
