from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# User role constant
ROLE_OWNER = "owner"


class User(UserMixin, db.Model):
    """Owner/User who manages the entire insurance business"""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(30))
    password_hash = db.Column(db.String(255), nullable=False)
    profile_picture_url = db.Column(db.String(500))
    role = db.Column(db.String(20), nullable=False, default=ROLE_OWNER)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    clients = db.relationship("Client", backref="owner", lazy="dynamic", cascade="all, delete-orphan")
    companies = db.relationship("Company", backref="owner", lazy="dynamic", cascade="all, delete-orphan")
    products = db.relationship("InsuranceProduct", backref="owner", lazy="dynamic", cascade="all, delete-orphan")
    policies = db.relationship("Policy", backref="owner", lazy="dynamic", cascade="all, delete-orphan")
    commission_rules = db.relationship("CommissionRule", backref="owner", lazy="dynamic", cascade="all, delete-orphan")
    remittances = db.relationship("PremiumRemittance", backref="owner", lazy="dynamic", cascade="all, delete-orphan")

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        return str(self.id)


class Client(db.Model):
    """Client who purchases insurance from the owner"""
    __tablename__ = "clients"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(30))
    address = db.Column(db.String(255))
    identification_type = db.Column(db.String(50))  # e.g., "National ID", "Passport", "Driver License"
    identification_number = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    policies = db.relationship("Policy", backref="client", lazy="dynamic", cascade="all, delete-orphan")
    remittances = db.relationship("PremiumRemittance", backref="client", lazy="dynamic", cascade="all, delete-orphan")


class Company(db.Model):
    """Insurance company that the owner works with"""
    __tablename__ = "companies"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False)
    contact_person = db.Column(db.String(120))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(30))
    address = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    products = db.relationship("InsuranceProduct", backref="company", lazy="dynamic", cascade="all, delete-orphan")
    commission_rules = db.relationship("CommissionRule", backref="company", lazy="dynamic", cascade="all, delete-orphan")
    policies = db.relationship("Policy", backref="company", lazy="dynamic")

    __table_args__ = (db.UniqueConstraint('user_id', 'name', name='uq_user_company'),)


class InsuranceProduct(db.Model):
    """Insurance product offered by a company"""
    __tablename__ = "insurance_products"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False, index=True)
    product_name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    base_commission_rate = db.Column(db.Float, nullable=False, default=10.0)  # Default commission %
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    commission_rules = db.relationship("CommissionRule", backref="product", lazy="dynamic", cascade="all, delete-orphan")
    policies = db.relationship("Policy", backref="product", lazy="dynamic")

    __table_args__ = (db.UniqueConstraint('user_id', 'company_id', 'product_name', name='uq_user_company_product'),)


class CommissionRule(db.Model):
    """Commission rules per company AND product combination"""
    __tablename__ = "commission_rules"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("insurance_products.id"), nullable=False, index=True)
    commission_percentage = db.Column(db.Float, nullable=False)  # Specific commission % for this company+product
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id', 'company_id', 'product_id', name='uq_user_company_product_commission'),)


class Policy(db.Model):
    """Insurance policy issued to a client"""
    __tablename__ = "policies"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("insurance_products.id"), nullable=False, index=True)
    
    policy_number = db.Column(db.String(100), nullable=False, unique=True, index=True)
    premium_amount = db.Column(db.Float, nullable=False)
    premium_frequency = db.Column(db.String(20), default="annual")  # monthly, quarterly, annual, one-time
    
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(30), default="active")  # active, expired, cancelled, pending
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    remittances = db.relationship("PremiumRemittance", backref="policy", lazy="dynamic", cascade="all, delete-orphan")

    def is_expired(self) -> bool:
        return date.today() > self.end_date

    def days_to_expiry(self) -> int:
        if self.is_expired():
            return 0
        return (self.end_date - date.today()).days

    def get_commission_percentage(self) -> float:
        """Get commission percentage for this policy based on company + product"""
        rule = CommissionRule.query.filter_by(
            user_id=self.user_id,
            company_id=self.company_id,
            product_id=self.product_id,
            is_active=True
        ).first()
        return rule.commission_percentage if rule else self.product.base_commission_rate

    def calculate_commission(self, premium_paid: float) -> float:
        """Calculate commission for a premium payment"""
        commission_rate = self.get_commission_percentage()
        return (premium_paid * commission_rate) / 100


class PremiumRemittance(db.Model):
    """Premium payment received from client (payment remittance tracking)"""
    __tablename__ = "premium_remittances"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False, index=True)
    policy_id = db.Column(db.Integer, db.ForeignKey("policies.id"), nullable=False, index=True)
    
    payment_method = db.Column(db.String(50), nullable=False)  # bank_transfer, cash, mobile_money
    amount = db.Column(db.Float, nullable=False)
    reference_number = db.Column(db.String(100))  # Bank reference, transaction ID, etc.
    
    payment_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(30), default="pending")  # pending, confirmed, remitted, cancelled
    
    commission_calculated = db.Column(db.Float)  # Commission amount for this remittance
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def calculate_commission(self) -> float:
        """Calculate commission for this payment"""
        return self.policy.calculate_commission(self.amount)

