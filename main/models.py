from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# Association constants
ROLE_CLIENT = "client"
ROLE_AGENT = "agent"
ROLE_ADMIN = "admin"


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(30))
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_CLIENT)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    policies = db.relationship("Policy", backref="client", lazy="dynamic", foreign_keys="Policy.client_id")
    agent_policies = db.relationship("Policy", backref="agent", lazy="dynamic", foreign_keys="Policy.agent_id")

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        return str(self.id)


class InsuranceCompany(db.Model):
    __tablename__ = "insurance_companies"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, unique=True)
    contact_email = db.Column(db.String(120))
    phone = db.Column(db.String(50))
    address = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    commission_rules = db.relationship("CommissionRule", backref="company", lazy="dynamic")
    policies = db.relationship("Policy", backref="company", lazy="dynamic")


class CommissionRule(db.Model):
    """
    Commission rules for each insurance company.
    For simplicity, use a flat percent for now.
    """
    __tablename__ = "commission_rules"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("insurance_companies.id"), nullable=False)
    description = db.Column(db.String(255))
    commission_percent = db.Column(db.Float, nullable=False, default=10.0)  # 10% default
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Policy(db.Model):
    __tablename__ = "policies"

    id = db.Column(db.Integer, primary_key=True)
    policy_number = db.Column(db.String(100), nullable=False, unique=True, index=True)
    client_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    agent_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey("insurance_companies.id"), nullable=False)

    product_name = db.Column(db.String(150), nullable=False)
    coverage_amount = db.Column(db.Float, nullable=False)
    premium_amount = db.Column(db.Float, nullable=False)
    premium_frequency = db.Column(db.String(20), default="annual")  # monthly, quarterly, annual, etc.

    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(30), default="active")  # active, expired, cancelled

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    premiums = db.relationship("PremiumTransaction", backref="policy", lazy="dynamic")
    commissions = db.relationship("CommissionTransaction", backref="policy", lazy="dynamic")

    def is_expired(self) -> bool:
        return date.today() > self.end_date

    def days_to_expiry(self) -> int:
        return (self.end_date - date.today()).days


class PremiumTransaction(db.Model):
    """
    Premiums received from clients on behalf of insurance companies.
    Not agent revenue.
    """
    __tablename__ = "premium_transactions"

    id = db.Column(db.Integer, primary_key=True)
    policy_id = db.Column(db.Integer, db.ForeignKey("policies.id"), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date_received = db.Column(db.DateTime, default=datetime.utcnow)
    payment_method = db.Column(db.String(50))
    reference = db.Column(db.String(120))
    is_remitted_to_company = db.Column(db.Boolean, default=False)
    date_remitted = db.Column(db.DateTime)


class CommissionTransaction(db.Model):
    """
    Commission revenue for the agent/corporate agent.
    Usually calculated as a percentage of premium.
    """
    __tablename__ = "commission_transactions"

    id = db.Column(db.Integer, primary_key=True)
    policy_id = db.Column(db.Integer, db.ForeignKey("policies.id"), nullable=False)
    premium_transaction_id = db.Column(db.Integer, db.ForeignKey("premium_transactions.id"))
    agent_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    amount = db.Column(db.Float, nullable=False)
    date_earned = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.String(255))

    premium_transaction = db.relationship("PremiumTransaction", backref="commission")


class ManualJournalEntry(db.Model):
    """
    Manual journal for adjustments (e.g., corrections to commission, premiums, etc.)
    """
    __tablename__ = "manual_journal_entries"

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.String(255), nullable=False)
    debit_account = db.Column(db.String(100), nullable=False)
    credit_account = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_by = db.relationship("User", backref="journal_entries")


class NotificationLog(db.Model):
    """
    Store reminder emails/SMS that have been sent.
    """
    __tablename__ = "notification_logs"

    id = db.Column(db.Integer, primary_key=True)
    policy_id = db.Column(db.Integer, db.ForeignKey("policies.id"), nullable=False)
    recipient_email = db.Column(db.String(120))
    notification_type = db.Column(db.String(50))  # e.g., "expiry_reminder"
    message = db.Column(db.Text)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
