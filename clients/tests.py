# clients/tests.py
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from .models import Client

User = get_user_model()


class ClientViewsTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin",
            password="testpass",
            role="SUPERADMIN",
        )
        self.client_user = Client.objects.create(
            full_name="John Doe",
            phone_number="0700000000",
        )

    def test_client_list_requires_login(self):
        resp = self.client.get(reverse("clients:client_list"))
        self.assertEqual(resp.status_code, 302)  # redirect to login

    def test_client_list_logged_in(self):
        self.client.login(username="admin", password="testpass")
        resp = self.client.get(reverse("clients:client_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "John Doe")

    def test_client_detail_view(self):
        self.client.login(username="admin", password="testpass")
        resp = self.client.get(reverse("clients:client_detail", args=[self.client_user.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "John Doe")
