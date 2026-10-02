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

