# reports/tests.py
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()


class ReportsViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin",
            password="testpass123",
            role="SUPERADMIN",
        )

    def test_dashboard_requires_login(self):
        resp = self.client.get(reverse("reports:dashboard"))
        self.assertEqual(resp.status_code, 302)

    def test_dashboard_logged_in(self):
        self.client.login(username="admin", password="testpass123")
        resp = self.client.get(reverse("reports:dashboard"))
        self.assertEqual(resp.status_code, 200)
