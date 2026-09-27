# commissions/urls.py

from django.urls import path
from . import views

app_name = "commissions"

urlpatterns = [
    path("", views.CommissionListView.as_view(), name="commission_list"),
    path("<int:pk>/", views.CommissionDetailView.as_view(), name="commission_detail"),
    path("summary/", views.CommissionSummaryView.as_view(), name="commission_summary"),
    path("payouts/", views.AgentPayoutListView.as_view(), name="payout_list"),
]
