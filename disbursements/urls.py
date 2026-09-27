# disbursements/urls.py
from django.urls import path

from .views import (
    DisbursementListView,
    DisbursementDetailView,
    DisbursementVoucherView,
    GenerateDisbursementView,
    DisbursementMarkProcessedView,
)

app_name = "disbursements"

urlpatterns = [
    path("", DisbursementListView.as_view(), name="disbursement_list"),
    path("generate/", GenerateDisbursementView.as_view(), name="disbursement_generate"),
    path("<int:pk>/", DisbursementDetailView.as_view(), name="disbursement_detail"),
    path("<int:pk>/mark-processed/", DisbursementMarkProcessedView.as_view(), name="disbursement_mark_processed"),
    path("<int:pk>/voucher/", DisbursementVoucherView.as_view(), name="disbursement_voucher"),
]
