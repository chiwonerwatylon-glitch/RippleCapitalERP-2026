# companies/urls.py
from django.urls import path

from .views import (
    CompanyListView,
    CompanyDetailView,
    CompanyCreateView,
    CompanyUpdateView,
    ClassOfBusinessCreateView,
)

app_name = "companies"

urlpatterns = [
    path("", CompanyListView.as_view(), name="company_list"),
    path("add/", CompanyCreateView.as_view(), name="company_add"),
    path("<int:pk>/", CompanyDetailView.as_view(), name="company_detail"),
    path("<int:pk>/edit/", CompanyUpdateView.as_view(), name="company_edit"),
    path("class-of-business/add/", ClassOfBusinessCreateView.as_view(), name="class_of_business_add"),
]
