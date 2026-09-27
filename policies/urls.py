# policies/urls.py
from django.urls import path
from .views import (
    PolicyListView,
    PolicyDetailView,
    PolicyCreateView,
    PolicyUpdateView,
    InstallmentScheduleView,
    PolicyRenewalView,
)

app_name = "policies"

urlpatterns = [
    path("", PolicyListView.as_view(), name="policy_list"),
    path("add/", PolicyCreateView.as_view(), name="policy_add"),
    path("<int:pk>/", PolicyDetailView.as_view(), name="policy_detail"),
    path("<int:pk>/edit/", PolicyUpdateView.as_view(), name="policy_edit"),
    path("<int:pk>/schedule/", InstallmentScheduleView.as_view(), name="installment_schedule"),
    path("<int:pk>/renew/", PolicyRenewalView.as_view(), name="policy_renew"),
]
