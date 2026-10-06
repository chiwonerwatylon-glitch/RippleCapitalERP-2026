from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# Association constants
ROLE_CLIENT = "client"
ROLE_OWNER = "owner"
ROLE_ADMIN = "admin"
ROLE_AGENT = "agent"


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(30))
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_OWNER)
    is_active = db.Column(db.Boolean, default=True)
    profile_picture = db.Column(db.String(500))  # URL or filename
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    clients_managed = db.relationship("Client", backref="owner", lazy="dynamic")
    companies = db.relationship("Company", backref="owner", lazy="dynamic")
    products = db.relationship("InsuranceProduct", backref="owner", lazy="dynamic")
    policies = db.relationship("Policy", backref="owner", lazy="dynamic", foreign_keys="Policy.owner_id")
    remittances = db.relationship("PremiumRemittance", backref="owner", lazy="dynamic")
    journal_entries = db.relationship("ManualJournalEntry", backref="created_by")

    @property
    def username(self):
        # Display name used by admin templates; stored in full_name.
        return self.full_name

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        return str(self.id)


class Client(db.Model):
    __tablename__ = "clients"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(30))
    address = db.Column(db.Text)
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    postal_code = db.Column(db.String(20))
    id_number = db.Column(db.String(50))  # National ID, Passport, etc.
    date_of_birth = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    policies = db.relationship("Policy", backref="client", lazy="dynamic", foreign_keys="Policy.client_id")

    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class Company(db.Model):
    __tablename__ = "companies"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    contact_email = db.Column(db.String(120))
    phone = db.Column(db.String(50))
    address = db.Column(db.Text)
    website = db.Column(db.String(255))
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    products = db.relationship("InsuranceProduct", backref="company", lazy="dynamic")
    commission_rules = db.relationship("CommissionRule", backref="company", lazy="dynamic", cascade="all, delete-orphan")


class InsuranceProduct(db.Model):
    __tablename__ = "insurance_products"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    coverage_type = db.Column(db.String(100))  # e.g., Life, Health, Auto
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    commission_rules = db.relationship("CommissionRule", backref="product", lazy="dynamic")
    policies = db.relationship("Policy", backref="product", lazy="dynamic")

    # company_id is nullable, so uniqueness of generic (company-less) products is
    # enforced in application code (see ensure_user_has_default_products).
    __table_args__ = (db.UniqueConstraint('owner_id', 'company_id', 'name', name='uq_product_per_company_owner'),)


class CommissionRule(db.Model):
    __tablename__ = "commission_rules"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("insurance_products.id"), nullable=False)
    commission_percent = db.Column(db.Float, nullable=False, default=10.0)
    description = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('company_id', 'product_id', name='uq_commission_company_product'),
    )


class Policy(db.Model):
    __tablename__ = "policies"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("insurance_products.id"), nullable=False)
    
    policy_number = db.Column(db.String(100), nullable=False, unique=True, index=True)
    coverage_amount = db.Column(db.Float, nullable=False)
    premium_amount = db.Column(db.Float, nullable=False)
    levy = db.Column(db.Float, nullable=False, default=0.0)
    selected_rate = db.Column(db.Float, nullable=True)  # Rate (%) selected for Motor/Homeowners
    premium_frequency = db.Column(db.String(20), default="annual")  # monthly, quarterly, annual
    
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(30), default="active")  # active, expired, cancelled
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    remittances = db.relationship("PremiumRemittance", backref="policy", lazy="dynamic", cascade="all, delete-orphan")

    def is_expired(self) -> bool:
        return date.today() > self.end_date

    def days_to_expiry(self) -> int:
        return (self.end_date - date.today()).days

    def total_premiums_paid(self) -> float:
        return sum(r.amount for r in self.remittances)

    def total_commission_earned(self) -> float:
        total = 0
        for remittance in self.remittances:
            rule = CommissionRule.query.filter_by(
                product_id=self.product_id,
                company_id=self.company_id,
                is_active=True
            ).first()
            if rule:
                total += remittance.amount * (rule.commission_percent / 100.0)
        return total


class PremiumRemittance(db.Model):
    __tablename__ = "premium_remittances"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    policy_id = db.Column(db.Integer, db.ForeignKey("policies.id"), nullable=False)
    
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)  # Bank Transfer, Cash, Mobile Money
    reference = db.Column(db.String(200))  # Transaction reference
    notes = db.Column(db.Text)
    
    date_received = db.Column(db.DateTime, default=datetime.utcnow)
    is_remitted_to_company = db.Column(db.Boolean, default=False)
    date_remitted = db.Column(db.DateTime)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ManualJournalEntry(db.Model):
    __tablename__ = "manual_journal_entries"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    
    date = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.String(255), nullable=False)
    debit_account = db.Column(db.String(100), nullable=False)
    credit_account = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class BulkUploadLog(db.Model):
    __tablename__ = "bulk_upload_logs"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    
    upload_type = db.Column(db.String(50), nullable=False)  # clients, policies
    file_name = db.Column(db.String(255))
    total_records = db.Column(db.Integer)
    successful_records = db.Column(db.Integer)
    failed_records = db.Column(db.Integer)
    error_log = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

