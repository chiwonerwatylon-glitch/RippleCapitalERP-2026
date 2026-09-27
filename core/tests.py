# core/tests.py
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()


class DashboardRouterTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin",
            password="testpass",
            role="SUPERADMIN",
        )
        self.accountant = User.objects.create_user(
            username="acc",
            password="testpass",
            role="ACCOUNTANT",
        )
        self.agent = User.objects.create_user(
            username="ag",
            password="testpass",
            role="AGENT",
        )

    def test_admin_redirect(self):
        self.client.login(username="admin", password="testpass")
        resp = self.client.get(reverse("core:dashboard-home"))
        self.assertRedirects(resp, reverse("core:dashboard-admin"))

    def test_accountant_redirect(self):
        self.client.login(username="acc", password="testpass")
        resp = self.client.get(reverse("core:dashboard-home"))
        self.assertRedirects(resp, reverse("core:dashboard-accountant"))

    def test_agent_redirect(self):
        self.client.login(username="ag", password="testpass")
        resp = self.client.get(reverse("core:dashboard-home"))
        self.assertRedirects(resp, reverse("core:dashboard-agent"))
