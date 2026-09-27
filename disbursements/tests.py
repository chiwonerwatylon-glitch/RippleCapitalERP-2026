# disbursements/tests.py
from datetime import date

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from companies.models import InsuranceCompany
from disbursements.models import Disbursement
from payments.models import Payment
from policies.models import Policy, PremiumInstallment
from commissions.models import Commission

User = get_user_model()


class DisbursementTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin",
            password="testpass",
            role="SUPERADMIN",
        )
        self.ic = InsuranceCompany.objects.create(
            name="Test Insurer",
            short_code="TI",
        )
        self.client_user = User.objects.create_user(
            username="acc",
            password="testpass",
            role="ACCOUNTANT",
        )

        from clients.models import Client
        self.client_obj = Client.objects.create(
            full_name="John Doe",
            phone_number="0700000000",
        )
        self.policy = Policy.objects.create(
            policy_number="P-001",
            client=self.client_obj,
            insurance_company=self.ic,
            class_of_business=None,
            sum_insured=1000000,
            premium_amount=100000,
            commission_rate=10,
            start_date=date(2026, 1, 1),
            end_date=date(2027, 1, 1),
            agent=self.client_user,
        )
        self.installment = PremiumInstallment.objects.create(
            policy=self.policy,
            installment_number=1,
            due_date=date(2026, 1, 1),
            amount_due=100000,
            amount_paid=0,
            balance=100000,
        )
        self.payment = Payment.objects.create(
            installment=self.installment,
            amount=100000,
            method="CASH",
            reference_number="REF123",
            received_by=self.admin,
            receipt_number="R001",
        )
        self.commission = Commission.objects.create(
            payment=self.payment,
            policy=self.policy,
            rate=10,
            amount=10000,
        )

    def test_disbursement_list_requires_login(self):
        resp = self.client.get(reverse("disbursements:disbursement_list"))
        self.assertEqual(resp.status_code, 302)

    def test_disbursement_generate_form_access(self):
        self.client.login(username="admin", password="testpass")
        resp = self.client.get(reverse("disbursements:disbursement_generate"))
        self.assertEqual(resp.status_code, 200)
