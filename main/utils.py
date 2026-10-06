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

class PremiumCalculator:
    """Calculate insurance premiums based on product type and sum insured."""
    
    # Product-specific rates and stamp duties
    MOTOR_PRODUCTS = ["Motor Comprehensive", "Third Party", "Full Third Party"]
    HOMEOWNERS_PRODUCT = "Homeowners"
    
    @staticmethod
    def calculate_premium(product_name, sum_insured, rate=None, stamp_duty_percent=None):
        """
        Calculate premium for insurance products.
        
        Args:
            product_name: Name of the insurance product
            sum_insured: Coverage/Sum Insured amount
            rate: Custom rate percentage (for manual products)
            stamp_duty_percent: Custom stamp duty percentage (for manual products)
        
        Returns:
            dict with keys: rate, stamp_duty, premium, or None if not calculable
        """
        if not sum_insured or sum_insured <= 0:
            return None
        
        # Motor vehicle insurance: 6% rate, 5% stamp duty on (sum_insured * rate)
        if product_name in PremiumCalculator.MOTOR_PRODUCTS:
            rate_pct = 6.0
            rate_amount = (sum_insured * rate_pct) / 100
            stamp_duty = (rate_amount * 5) / 100
            total = rate_amount + stamp_duty
            
            return {
                "rate_percent": rate_pct,
                "rate_amount": round(rate_amount, 2),
                "stamp_duty_percent": 5.0,
                "stamp_duty": round(stamp_duty, 2),
                "total_premium": round(total, 2),
            }
        
        # Homeowners insurance: 0.125% rate, 5% stamp duty on (sum_insured * rate)
        elif product_name == PremiumCalculator.HOMEOWNERS_PRODUCT:
            rate_pct = 0.125
            rate_amount = (sum_insured * rate_pct) / 100
            stamp_duty = (rate_amount * 5) / 100
            total = rate_amount + stamp_duty
            
            return {
                "rate_percent": rate_pct,
                "rate_amount": round(rate_amount, 2),
                "stamp_duty_percent": 5.0,
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
        frequency: "termly" (3 months), "annually" (12 months), or "monthly" (1 month)
    
    Returns:
        datetime.date: Calculated end date
    """
    if not isinstance(start_date, date):
        return start_date
    
    if frequency == "termly" or frequency == "quarterly":
        # Termly = 3 months
        end_date = start_date + timedelta(days=92)  # approximately 3 months
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

