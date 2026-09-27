# clients/urls.py
from django.urls import path
from .views import (
    ClientListView,
    ClientDetailView,
    ClientCreateView,
    ClientUpdateView,
    ClientStatementView,
)

app_name = "clients"

urlpatterns = [
    path("", ClientListView.as_view(), name="client_list"),
    path("add/", ClientCreateView.as_view(), name="client_add"),
    path("<int:pk>/", ClientDetailView.as_view(), name="client_detail"),
    path("<int:pk>/edit/", ClientUpdateView.as_view(), name="client_edit"),
    path("<int:pk>/statement/", ClientStatementView.as_view(), name="client_statement"),
]
