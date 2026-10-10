from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user
from datetime import datetime, date, timedelta
import uuid
from .models import Policy, User, ROLE_ADMIN, ROLE_AGENT

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
    """Get the account owner ID that scopes business data.

    Staff (admin/agent) and clients point to the owner via account_owner_id;
    owners (and users without a link) use their own ID.
    """
    from flask_login import current_user as cu
    user = user or cu

    if not user or not user.is_authenticated:
        return None

    if getattr(user, "account_owner_id", None):
        return user.account_owner_id
    # Staff created without a link (e.g. by seed/startup scripts) share the owner's data.
    if user.role in (ROLE_ADMIN, ROLE_AGENT):
        owner = User.query.filter_by(role="owner").order_by(User.id).first()
        if owner:
            return owner.id
    return user.id

# ==================== PREMIUM CALCULATION LOGIC ====================

MOTOR_PRODUCTS = ["Motor Comprehensive", "Third Party", "Full Third Party"]
HOMEOWNERS_PRODUCT = "Homeowners"

# Rate ranges in percent (min, max, default)
MOTOR_RATE_RANGE = {"min": 3.5, "max": 10.0, "default": 6.0}
HOMEOWNERS_RATE_RANGE = {"min": 0.125, "max": 0.3, "default": 0.125}

# Stamp duty percentage applied to the rate amount for Motor and Homeowners
DEFAULT_STAMP_DUTY_PERCENT = 5.0

# Days covered per premium frequency (kept for backward compatibility)
DAYS_BY_FREQUENCY = {
    "monthly": 30,
    "termly": 122,  # 4 months
    "quarterly": 122,
    "annual": 365,
    "annually": 365,
}


def get_days_in_period(frequency):
    """Return the number of days covered for a premium frequency (defaults to annual)."""
    return DAYS_BY_FREQUENCY.get(frequency, 365)


def calculate_actual_days(start_date, end_date):
    """
    Calculate actual calendar days between start_date and end_date (inclusive).
    
    Args:
        start_date: Policy start date (datetime.date or string 'YYYY-MM-DD')
        end_date: Policy end date (datetime.date or string 'YYYY-MM-DD')
    
    Returns:
        int: Number of days between dates (inclusive)
    """
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
    
    if not start_date or not end_date or start_date >= end_date:
        return 0
    
    # Calculate days inclusive (add 1 to include both start and end dates)
    return (end_date - start_date).days + 1


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

            # Annual amount: sum insured x rate, then stamp duty (5%) on that amount
            annual_rate_amount = sum_insured * rate_pct / 100
            annual_stamp_duty = annual_rate_amount * DEFAULT_STAMP_DUTY_PERCENT / 100
            annual_total = annual_rate_amount + annual_stamp_duty

            # Pro-rate for the period: x days / 365 (kept unrounded until the final total)
            factor = days / 365
            rate_amount = annual_rate_amount * factor
            stamp_duty = annual_stamp_duty * factor
            total = annual_total * factor

            return {
                "rate_percent": rate_pct,
                "selected_rate": rate_pct,
                "days_in_period": days,
                "rate_amount": round(rate_amount, 2),
                "stamp_duty_percent": DEFAULT_STAMP_DUTY_PERCENT,
                "stamp_duty": round(stamp_duty, 2),
                "total_premium": round(total, 2),
                "total_premium_exact": total,
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
                "total_premium_exact": total,
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
        days = calculate_actual_days(start_date, end_date)
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
    
    For monthly: end date is the same day of the next month
    For termly (4 months): end date is the same day 4 months later
    For annual (12 months): end date is the same day 12 months later
    
    Example: Start 6 Oct → Monthly ends 5 Nov (30 days later)
    
    Args:
        start_date: Policy start date (datetime.date)
        frequency: "termly" (4 months), "annually" (12 months), or "monthly" (1 month)
    
    Returns:
        datetime.date: Calculated end date
    """
    if not isinstance(start_date, date):
        return start_date
    
    if frequency == "termly" or frequency == "quarterly":
        # Termly = 4 months (calculate by adding months, then subtract 1 day for end date)
        # Start: Oct 6 → +4 months = Dec 6 → subtract 1 day = Dec 5
        month = start_date.month + 4
        year = start_date.year
        while month > 12:
            month -= 12
            year += 1
        # Get the same day 4 months later
        try:
            end_date = date(year, month, start_date.day)
        except ValueError:
            # Handle edge case (e.g., Jan 31 + 1 month)
            end_date = date(year, month, 28) if month == 2 else date(year, month, 30)
        # Subtract 1 day to make it the day before the 4-month anniversary
        end_date = end_date - timedelta(days=1)
    elif frequency == "annually" or frequency == "annual":
        # Annual = 12 months (same logic as termly but +12 months)
        month = start_date.month + 12
        year = start_date.year
        while month > 12:
            month -= 12
            year += 1
        try:
            end_date = date(year, month, start_date.day)
        except ValueError:
            end_date = date(year, month, 28) if month == 2 else date(year, month, 30)
        # Subtract 1 day
        end_date = end_date - timedelta(days=1)
    elif frequency == "monthly":
        # Monthly = 1 month (add 1 month, subtract 1 day)
        month = start_date.month + 1
        year = start_date.year
        if month > 12:
            month -= 12
            year += 1
        try:
            end_date = date(year, month, start_date.day)
        except ValueError:
            # Handle edge case (e.g., Jan 31 + 1 month = Feb 31, which doesn't exist)
            end_date = date(year, month, 28) if month == 2 else date(year, month, 30)
        # Subtract 1 day to make it the day before the monthly anniversary
        end_date = end_date - timedelta(days=1)
    else:
        # Default to annual
        month = start_date.month + 12
        year = start_date.year
        while month > 12:
            month -= 12
            year += 1
        try:
            end_date = date(year, month, start_date.day)
        except ValueError:
            end_date = date(year, month, 28) if month == 2 else date(year, month, 30)
        end_date = end_date - timedelta(days=1)
    
    return end_date

