"""
commissions/tests.py

Unit tests for the Commissions app.
"""

from decimal import Decimal
from datetime import date

from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model

from companies.models import InsuranceCompany, ClassOfBusiness
from clients.models import Client
from policies.models import Policy
from payments.models import Payment
from .models import Commission, CommissionStatus, AgentCommissionPayout
from . import services


User = get_user_model()


class CommissionModelTests(TestCase):
    def setUp(self):
        self.company = InsuranceCompany.objects.create(
            name="Test Insurer", short_code="TI"
        )
        self.class_of_business = ClassOfBusiness.objects.create(
            insurance_company=self.company,
            name="Motor",
            default_commission_rate=Decimal("10.00"),
        )
        self.agent = User.objects.create_user(
            username="agent1",
            password="testpass",
            role="AGENT",
        )
        self.client = Client.objects.create(
            full_name="John Doe",
            phone_number="0700000000",
        )
        self.policy = Policy.objects.create(
            policy_number="P-001",
            client=self.client,
            insurance_company=self.company,
            class_of_business=self.class_of_business,
            sum_insured=Decimal("1000000"),
            premium_amount=Decimal("100000"),
            commission_rate=Decimal("10.00"),
            start_date=date(2026, 1, 1),
            end_date=date(2027, 1, 1),
            agent=self.agent,
        )
        self.user = User.objects.create_user(
            username="admin",
            password="testpass",
            role="ACCOUNTANT",
        )
        self.payment = Payment.objects.create(
            installment=self.policy.installments.create(
                installment_number=1,
                due_date=date(2026, 1, 1),
                amount_due=Decimal("100000"),
                balance=Decimal("100000"),
            ),
            amount=Decimal("100000"),
            method="CASH",
            reference_number="REF123",
            received_by=self.user,
            receipt_number="R001",
        )
        # In your real project, a signal creates Commission automatically.
        # For this test, we'll create it manually.
        self.commission = Commission.objects.create(
            payment=self.payment,
            policy=self.policy,
            rate=self.policy.commission_rate,
            amount=Decimal("10000"),  # 10% of 100,000
        )

    def test_commission_net_amount_initially_equals_amount(self):
        self.assertEqual(self.commission.net_amount, self.commission.amount)

    def test_confirm_commission(self):
        services.confirm_commission(self.commission, user=self.user)
        self.commission.refresh_from_db()
        self.assertEqual(self.commission.status, CommissionStatus.CONFIRMED)
        self.assertIsNotNone(self.commission.confirmed_at)


class CommissionServiceTests(TestCase):
    def setUp(self):
        self.company = InsuranceCompany.objects.create(
            name="Test Insurer", short_code="TI"
        )
        self.class_of_business = ClassOfBusiness.objects.create(
            insurance_company=self.company,
            name="Motor",
            default_commission_rate=Decimal("10.00"),
        )
        self.agent = User.objects.create_user(
            username="agent1",
            password="testpass",
            role="AGENT",
        )
        self.client = Client.objects.create(
            full_name="John Doe",
            phone_number="0700000000",
        )
        self.policy = Policy.objects.create(
            policy_number="P-001",
            client=self.client,
            insurance_company=self.company,
            class_of_business=self.class_of_business,
            sum_insured=Decimal("1000000"),
            premium_amount=Decimal("100000"),
            commission_rate=Decimal("10.00"),
            start_date=date(2026, 1, 1),
            end_date=date(2027, 1, 1),
            agent=self.agent,
        )
        self.user = User.objects.create_user(
            username="admin",
            password="testpass",
            role="ACCOUNTANT",
        )
        self.installment = self.policy.installments.create(
            installment_number=1,
            due_date=date(2026, 1, 1),
            amount_due=Decimal("100000"),
            balance=Decimal("100000"),
        )
        self.payment = Payment.objects.create(
            installment=self.installment,
            amount=Decimal("100000"),
            method="CASH",
            reference_number="REF123",
            received_by=self.user,
            receipt_number="R001",
        )
        self.commission = Commission.objects.create(
            payment=self.payment,
            policy=self.policy,
            rate=self.policy.commission_rate,
            amount=Decimal("10000"),
        )

    def test_reverse_commission_full(self):
        services.confirm_commission(self.commission, user=self.user)
        adj = services.reverse_commission(
            self.commission,
            reason="PAYMENT_REVERSED",
            user=self.user,
        )
        self.commission.refresh_from_db()
        self.assertLess(adj.adjustment_amount, 0)  # negative
        self.assertEqual(self.commission.net_amount, Decimal("0.00"))
        self.assertEqual(self.commission.status, CommissionStatus.REVERSED)

    def test_generate_agent_payout(self):
        services.confirm_commission(self.commission, user=self.user)
        payout = services.generate_agent_payout(
            agent=self.agent,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 12, 31),
            user=self.user,
        )
        self.assertIsInstance(payout, AgentCommissionPayout)
        self.assertEqual(payout.total_amount, Decimal("10000"))
        self.assertEqual(payout.agent, self.agent)
