import re

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from .models import db, User, ROLE_ADMIN
from .utils import role_required

# Safely import optional models
try:
    from .models import (
        Company,
        CommissionRule,
        ManualJournalEntry,
        ROLE_OWNER,
    )
    HAS_NEW_MODELS = True
except ImportError:
    HAS_NEW_MODELS = False

try:
    from .forms import CompanyForm, CommissionRuleForm, ManualJournalForm
except ImportError:
    ManualJournalForm = None

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/")
@login_required
@role_required(ROLE_ADMIN)
def dashboard():
    if HAS_NEW_MODELS:
        companies_count = Company.query.count()
    else:
        try:
            from .models import InsuranceCompany
            companies_count = InsuranceCompany.query.count()
        except:
            companies_count = 0
    
    users_count = User.query.count()
    return render_template("admin_dashboard.html",
                           companies_count=companies_count,
                           users_count=users_count)


@admin_bp.route("/users")
@login_required
@role_required(ROLE_ADMIN)
def users():
    try:
        all_users = User.query.order_by(User.id).all()
    except Exception as e:
        flash(f"Error loading users: {str(e)}", "danger")
        all_users = []
    return render_template("admin_users.html", users=all_users)


@admin_bp.route("/users/add", methods=["GET", "POST"])
@login_required
@role_required(ROLE_ADMIN)
def add_user():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        email = (request.form.get("email") or "").strip()
        role = (request.form.get("role") or "").strip()

        if not username or not email or not role:
            flash("Username, email and role are required.", "danger")
            return render_template("admin_add_user.html")

        try:
            # The username is stored in User.full_name.
            if User.query.filter_by(full_name=username).first():
                flash("Username already exists.", "danger")
                return render_template("admin_add_user.html")
            if User.query.filter_by(email=email).first():
                flash("A user with that email already exists.", "danger")
                return render_template("admin_add_user.html")

            user = User(full_name=username, email=email, role=role, is_active=True)
            user.set_password("password2026")
            db.session.add(user)
            db.session.commit()
            flash(f"User '{username}' created successfully.", "success")
            return redirect(url_for("admin.users"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error creating user: {str(e)}", "danger")
            return render_template("admin_add_user.html")

    return render_template("admin_add_user.html")


@admin_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@role_required(ROLE_ADMIN)
def edit_user(user_id):
    user = User.query.get_or_404(user_id)

    if request.method == "POST":
        try:
            email = (request.form.get("email") or "").strip()
            role = (request.form.get("role") or "").strip()
            if not email or not role:
                flash("Email and role are required.", "danger")
                return render_template("admin_edit_user.html", user=user)

            if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
                flash("Please enter a valid email address.", "danger")
                return render_template("admin_edit_user.html", user=user)

            email_changed = email.lower() != (user.email or "").lower()
            if email_changed:
                existing = User.query.filter(
                    db.func.lower(User.email) == email.lower(),
                    User.id != user.id,
                ).first()
                if existing:
                    flash("That email address is already in use by another user.", "danger")
                    return render_template("admin_edit_user.html", user=user)

            old_email = user.email
            user.email = email
            user.role = role
            db.session.commit()
            if email_changed:
                flash(
                    f"Email for '{user.username}' changed by admin from {old_email} to {email}.",
                    "info",
                )
            flash(f"User '{user.username}' updated successfully.", "success")
            return redirect(url_for("admin.users"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error updating user: {str(e)}", "danger")
            return render_template("admin_edit_user.html", user=user)

    return render_template("admin_edit_user.html", user=user)


@admin_bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@login_required
@role_required(ROLE_ADMIN)
def toggle_user(user_id):
    user = User.query.get_or_404(user_id)
    try:
        user.is_active = not user.is_active
        db.session.commit()
        status = "activated" if user.is_active else "deactivated"
        flash(f"User '{user.username}' {status}.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating user status: {str(e)}", "danger")
    return redirect(url_for("admin.users"))


@admin_bp.route("/companies")
@login_required
@role_required(ROLE_ADMIN)
def companies():
    all_companies = []
    try:
        if HAS_NEW_MODELS:
            all_companies = Company.query.order_by(Company.id).all()
        else:
            from .models import InsuranceCompany
            all_companies = InsuranceCompany.query.all()
    except Exception as e:
        flash(f"Error loading companies: {str(e)}", "danger")
    return render_template("admin_companies.html", companies=all_companies)


@admin_bp.route("/companies/add", methods=["GET", "POST"])
@login_required
@role_required(ROLE_ADMIN)
def add_company():
    if not HAS_NEW_MODELS:
        flash("Company feature not available in this configuration.", "info")
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        contact_email = (request.form.get("contact_email") or "").strip()

        if not name:
            flash("Company name is required.", "danger")
            return render_template("admin_add_company.html")

        try:
            company = Company(
                owner_id=current_user.id,
                name=name,
                contact_email=contact_email,
            )
            db.session.add(company)
            db.session.commit()
            flash(f"Company '{name}' created successfully.", "success")
            return redirect(url_for("admin.companies"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error creating company: {str(e)}", "danger")
            return render_template("admin_add_company.html")

    return render_template("admin_add_company.html")


@admin_bp.route("/manual-journal", methods=["GET", "POST"])
@login_required
def manual_journal():
    if not HAS_NEW_MODELS or ManualJournalForm is None:
        flash("Journal feature not available in this configuration.", "info")
        return redirect(url_for("admin.dashboard"))
    
    form = ManualJournalForm()
    if form.validate_on_submit():
        try:
            entry = ManualJournalEntry(
                owner_id=current_user.id,
                description=form.description.data,
                debit_account=form.debit_account.data,
                credit_account=form.credit_account.data,
                amount=form.amount.data,
            )
            db.session.add(entry)
            db.session.commit()
            flash("Journal entry posted.", "success")
        except Exception as e:
            flash(f"Error saving journal entry: {str(e)}", "danger")
        return redirect(url_for("admin.manual_journal"))

    try:
        entries = ManualJournalEntry.query.filter_by(owner_id=current_user.id).order_by(
            ManualJournalEntry.date.desc()
        ).limit(50).all()
    except:
        entries = []
    
    return render_template("manual_journal.html", form=form, entries=entries)

