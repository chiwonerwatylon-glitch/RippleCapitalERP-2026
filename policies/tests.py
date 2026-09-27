# policies/tests.py
from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from clients.models import Client
from companies.models import InsuranceCompany, ClassOfBusiness
from .models import Policy, PremiumInstallment

User = get_user_model()


class PolicyTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin",
            password="testpass123",
            role="SUPERADMIN",
        )
        self.client_obj = Client.objects.create(
            full_name="John Doe",
            phone_number="0700000000",
        )
        self.ic = InsuranceCompany.objects.create(
            name="Test Insurer",
            short_code="TI",
        )
        self.cob = ClassOfBusiness.objects.create(
            insurance_company=self.ic,
            name="Motor",
            default_commission_rate=Decimal("10.00"),
        )

    def test_policy_creation_creates_installments(self):
        self.client.login(username="admin", password="testpass123")
        resp = self.client.post(reverse("policies:policy_add"), {
            "policy_number": "P-001",
            "client": self.client_obj.id,
            "insurance_company": self.ic.id,
            "class_of_business": self.cob.id,
            "sum_insured": "1000000",
            "premium_amount": "100000",
            "commission_rate": "10.00",
            "start_date": "2026-01-01",
            "end_date": "2027-01-01",
            "status": "ACTIVE",
            "agent": self.admin.id,
        })
        self.assertEqual(resp.status_code, 302)
        policy = Policy.objects.get(policy_number="P-001")
        self.assertTrue(policy.installments.exists())
