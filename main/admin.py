from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from .models import (
    db,
    User,
    Company,
    CommissionRule,
    ManualJournalEntry,
    ROLE_ADMIN,
    ROLE_OWNER,
)
from .forms import CompanyForm, CommissionRuleForm, ManualJournalForm
from .utils import role_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/")
@login_required
@role_required(ROLE_ADMIN)
def dashboard():
    companies_count = Company.query.count()
    users_count = User.query.count()
    return render_template("admin_dashboard.html",
                           companies_count=companies_count,
                           users_count=users_count)


@admin_bp.route("/manual-journal", methods=["GET", "POST"])
@login_required
@role_required(ROLE_ADMIN, ROLE_OWNER)
def manual_journal():
    form = ManualJournalForm()
    if form.validate_on_submit():
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
        return redirect(url_for("admin.manual_journal"))

    entries = ManualJournalEntry.query.filter_by(owner_id=current_user.id).order_by(
        ManualJournalEntry.date.desc()
    ).limit(50).all()
    return render_template("manual_journal.html", form=form, entries=entries)

