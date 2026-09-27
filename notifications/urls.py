# notifications/urls.py
from django.urls import path
from .views import NotificationLogListView

app_name = "notifications"

urlpatterns = [
    path("logs/", NotificationLogListView.as_view(), name="notification_log_list"),
]
