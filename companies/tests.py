# companies/tests.py
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from .models import InsuranceCompany

User = get_user_model()


class CompanyViewsTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin",
            password="testpass",
            role="SUPERADMIN",
        )
        self.company = InsuranceCompany.objects.create(
            name="Test Insurer",
            short_code="TI",
        )

    def test_company_list_requires_login(self):
        resp = self.client.get(reverse("companies:company_list"))
        self.assertEqual(resp.status_code, 302)

    def test_company_list_logged_in(self):
        self.client.login(username="admin", password="testpass")
        resp = self.client.get(reverse("companies:company_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Test Insurer")

    def test_company_detail_view(self):
        self.client.login(username="admin", password="testpass")
        resp = self.client.get(reverse("companies:company_detail", args=[self.company.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Test Insurer")
