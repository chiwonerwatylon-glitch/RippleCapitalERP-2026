# payments/tests.py
from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from clients.models import Client
from companies.models import InsuranceCompany, ClassOfBusiness
from policies.models import Policy, PremiumInstallment
from .models import Payment

User = get_user_model()


class PaymentFlowTests(TestCase):
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
        self.policy = Policy.objects.create(
            policy_number="P-001",
            client=self.client_obj,
            insurance_company=self.ic,
            class_of_business=self.cob,
            sum_insured=Decimal("1000000"),
            premium_amount=Decimal("100000"),
            commission_rate=Decimal("10.00"),
            start_date=date(2026, 1, 1),
            end_date=date(2027, 1, 1),
            agent=self.admin,
        )
        self.installment = PremiumInstallment.objects.create(
            policy=self.policy,
            installment_number=1,
            due_date=date(2026, 1, 15),
            amount_due=Decimal("100000"),
            amount_paid=Decimal("0.00"),
            balance=Decimal("100000"),
            status="PENDING",
        )

    def test_payment_creation_updates_installment(self):
        self.client.login(username="admin", password="testpass123")
        resp = self.client.post(reverse("payments:payment_add"), {
            "installment": self.installment.id,
            "amount": "100000",
            "method": "CASH",
            "reference_number": "REF123",
        })
        self.assertEqual(resp.status_code, 302)
        payment = Payment.objects.first()
        self.assertIsNotNone(payment)
        self.installment.refresh_from_db()
        self.assertEqual(self.installment.amount_paid, Decimal("100000"))
        self.assertEqual(self.installment.balance, Decimal("0"))
        self.assertEqual(self.installment.status, "PAID")
