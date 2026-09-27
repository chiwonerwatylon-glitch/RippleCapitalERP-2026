# payments/urls.py
from django.urls import path

from .views import PaymentListView, PaymentCreateView, PaymentDetailView

app_name = "payments"

urlpatterns = [
    path("", PaymentListView.as_view(), name="payment_list"),
    path("add/", PaymentCreateView.as_view(), name="payment_add"),
    path("<int:pk>/", PaymentDetailView.as_view(), name="payment_detail"),
]
