from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user
from datetime import datetime, date, timedelta
import uuid
from .models import Policy

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if current_user.role not in roles:
                flash(f"You need {' or '.join(roles)} role to access this page.", "danger")
                return redirect(url_for("core.dashboard"))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def get_account_owner_id(user=None):
    """Get the account owner ID (for owner/admin/agent, it's their own ID; for clients, it's owner_id from context)."""
    from flask_login import current_user as cu
    user = user or cu
    
    if not user or not user.is_authenticated:
        return None
    
    # Import here to avoid circular imports
    from .models import ROLE_OWNER, ROLE_ADMIN, ROLE_AGENT, ROLE_CLIENT
    
    if user.role in [ROLE_OWNER, ROLE_ADMIN, ROLE_AGENT]:
        return user.id
    # For clients, we'd need context, but this shouldn't happen in most cases
    return user.id

# ==================== PREMIUM CALCULATION LOGIC ====================

MOTOR_PRODUCTS = ["Motor Comprehensive", "Third Party", "Full Third Party"]
HOMEOWNERS_PRODUCT = "Homeowners"

# Rate ranges in percent (min, max, default)
MOTOR_RATE_RANGE = {"min": 3.5, "max": 10.0, "default": 6.0}
HOMEOWNERS_RATE_RANGE = {"min": 0.125, "max": 0.3, "default": 0.125}

# Stamp duty percentage applied to the rate amount for Motor and Homeowners
DEFAULT_STAMP_DUTY_PERCENT = 5.0

# Days covered per premium frequency
DAYS_BY_FREQUENCY = {
    "monthly": 30,
    "termly": 120,  # 4 months
    "quarterly": 120,
    "annual": 365,
    "annually": 365,
}


def get_days_in_period(frequency):
    """Return the number of days covered for a premium frequency (defaults to annual)."""
    return DAYS_BY_FREQUENCY.get(frequency, 365)


class PremiumCalculator:
    """Calculate insurance premiums based on product type and sum insured."""
    
    # Product-specific rates and stamp duties
    MOTOR_PRODUCTS = MOTOR_PRODUCTS
    HOMEOWNERS_PRODUCT = HOMEOWNERS_PRODUCT

    @staticmethod
    def get_rate_range(product_name):
        """Return the allowed rate range dict for a product, or None for manual products."""
        if product_name in MOTOR_PRODUCTS:
            return MOTOR_RATE_RANGE
        if product_name == HOMEOWNERS_PRODUCT:
            return HOMEOWNERS_RATE_RANGE
        return None
    
    @staticmethod
    def calculate_premium(product_name, sum_insured, rate=None, stamp_duty_percent=None,
                          selected_rate=None, days_in_period=365):
        """
        Calculate premium for insurance products.
        
        Args:
            product_name: Name of the insurance product
            sum_insured: Coverage/Sum Insured amount
            rate: Custom rate percentage (for manual products)
            stamp_duty_percent: Custom stamp duty percentage (for manual products)
            selected_rate: User-selected rate percentage (Motor/Homeowners), must be
                within the product's allowed range. Defaults to the range default.
            days_in_period: Days covered, used to pro-rate Motor/Homeowners premiums
        
        Returns:
            dict with premium components, or None if not calculable

        Raises:
            ValueError: if selected_rate is outside the allowed range
        """
        if not sum_insured or sum_insured <= 0:
            return None
        
        rate_range = PremiumCalculator.get_rate_range(product_name)
        if rate_range is not None:
            rate_pct = rate_range["default"] if selected_rate is None else float(selected_rate)
            if rate_pct < rate_range["min"] or rate_pct > rate_range["max"]:
                raise ValueError(
                    f"Rate must be between {rate_range['min']}% and {rate_range['max']}% for this product."
                )
            days = int(days_in_period or 365)
            if days <= 0:
                raise ValueError("Days in period must be greater than 0.")

            # rate_amount = sum_insured * rate% * days / 365
            rate_amount = (sum_insured * rate_pct * days) / (100 * 365)
            stamp_duty = (rate_amount * DEFAULT_STAMP_DUTY_PERCENT) / 100
            total = rate_amount + stamp_duty
            
            return {
                "rate_percent": rate_pct,
                "selected_rate": rate_pct,
                "days_in_period": days,
                "rate_amount": round(rate_amount, 2),
                "stamp_duty_percent": DEFAULT_STAMP_DUTY_PERCENT,
                "stamp_duty": round(stamp_duty, 2),
                "total_premium": round(total, 2),
            }
        
        # Manual calculation for other products
        elif rate is not None and stamp_duty_percent is not None:
            rate_amount = (sum_insured * rate) / 100
            stamp_duty = (rate_amount * stamp_duty_percent) / 100
            total = rate_amount + stamp_duty
            
            return {
                "rate_percent": rate,
                "rate_amount": round(rate_amount, 2),
                "stamp_duty_percent": stamp_duty_percent,
                "stamp_duty": round(stamp_duty, 2),
                "total_premium": round(total, 2),
            }
        
        # Not calculable yet (waiting for manual input)
        return None
    
    @staticmethod
    def calculate_daily_premium(total_premium, start_date, end_date):
        """
        Calculate daily premium by dividing total premium by number of days.
        
        Args:
            total_premium: Total premium amount
            start_date: Policy start date (datetime.date)
            end_date: Policy end date (datetime.date)
        
        Returns:
            float: Daily premium amount
        """
        if not start_date or not end_date or start_date >= end_date:
            return 0
        
        days = (end_date - start_date).days
        if days <= 0:
            return 0
        
        return round(total_premium / days, 2)


def generate_policy_number():
    """Generate a unique policy number."""
    # Format: POL-YYYYMMDD-XXXXX (timestamp + random component)
    timestamp = datetime.now().strftime("%Y%m%d")
    random_suffix = str(uuid.uuid4().hex[:5]).upper()
    return f"POL-{timestamp}-{random_suffix}"


def calculate_end_date_from_frequency(start_date, frequency):
    """
    Calculate end date based on premium frequency and start date.
    
    Args:
        start_date: Policy start date (datetime.date)
        frequency: "termly" (4 months), "annually" (12 months), or "monthly" (1 month)
    
    Returns:
        datetime.date: Calculated end date
    """
    if not isinstance(start_date, date):
        return start_date
    
    if frequency == "termly" or frequency == "quarterly":
        # Termly = 4 months = 120 days
        end_date = start_date + timedelta(days=120)
    elif frequency == "annually" or frequency == "annual":
        # Annual = 12 months
        end_date = start_date + timedelta(days=365)
    elif frequency == "monthly":
        # Monthly = 1 month
        end_date = start_date + timedelta(days=30)
    else:
        # Default to annual
        end_date = start_date + timedelta(days=365)
    
    return end_date

