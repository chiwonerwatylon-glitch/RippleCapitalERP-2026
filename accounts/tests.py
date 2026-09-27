# accounts/tests.py
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()


class LoginTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123",
            role="ACCOUNTANT",
        )

    def test_login_redirects_to_dashboard(self):
        resp = self.client.post(reverse("accounts:login"), {
            "username": "testuser",
            "password": "testpass123",
        })
        self.assertRedirects(resp, reverse("core:dashboard-home"))


class UserAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin",
            password="testpass123",
            role="SUPERADMIN",
        )
        self.user = User.objects.create_user(
            username="user1",
            password="testpass123",
            role="AGENT",
        )

    def test_user_list_requires_admin(self):
        # Not logged in → redirect to login
        resp = self.client.get(reverse("accounts:user_list"))
        self.assertEqual(resp.status_code, 302)

        # Logged in as admin → access granted
        self.client.login(username="admin", password="testpass123")
        resp = self.client.get(reverse("accounts:user_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "user1")
