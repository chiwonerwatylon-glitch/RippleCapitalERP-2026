# notifications/tests.py
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from .models import NotificationLog, NotificationChannel, NotificationType

User = get_user_model()


class NotificationLogViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin",
            password="testpass123",
            role="SUPERADMIN",
        )
        self.log = NotificationLog.objects.create(
            channel=NotificationChannel.EMAIL,
            notification_type=NotificationType.PREMIUM_DUE,
            recipient="client@example.com",
        )

    def test_requires_login(self):
        resp = self.client.get(reverse("notifications:notification_log_list"))
        self.assertEqual(resp.status_code, 302)

    def test_admin_can_view_logs(self):
        self.client.login(username="admin", password="testpass123")
        resp = self.client.get(reverse("notifications:notification_log_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "client@example.com")
