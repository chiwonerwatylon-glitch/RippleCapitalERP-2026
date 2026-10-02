from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from .models import db, User, InsuranceCompany, CommissionRule, ManualJournalEntry, ROLE_ADMIN
from .forms import CompanyForm, CommissionRuleForm, ManualJournalForm
from .utils import role_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/")
@login_required
@role_required(ROLE_ADMIN)
def dashboard():
    companies_count = InsuranceCompany.query.count()
    users_count = User.query.count()
    return render_template("admin_dashboard.html",
                           companies_count=companies_count,
                           users_count=users_count)


@admin_bp.route("/companies")
@login_required
@role_required(ROLE_ADMIN)
def companies():
    companies = InsuranceCompany.query.order_by(InsuranceCompany.name).all()
    return render_template("company_list.html", companies=companies)


@admin_bp.route("/companies/new", methods=["GET", "POST"])
@login_required
@role_required(ROLE_ADMIN)
def company_create():
    form = CompanyForm()
    if form.validate_on_submit():
        company = InsuranceCompany(
            name=form.name.data,
            contact_email=form.contact_email.data,
            phone=form.phone.data,
            address=form.address.data
        )
        db.session.add(company)
        db.session.commit()
        flash("Insurance company created.", "success")
        return redirect(url_for("admin.companies"))
    return render_template("company_detail.html", form=form, company=None)


@admin_bp.route("/companies/<int:company_id>", methods=["GET", "POST"])
@login_required
@role_required(ROLE_ADMIN)
def company_edit(company_id):
    company = InsuranceCompany.query.get_or_404(company_id)
    form = CompanyForm(obj=company)
    if form.validate_on_submit():
        form.populate_obj(company)
        db.session.commit()
        flash("Company updated.", "success")
        return redirect(url_for("admin.companies"))
    return render_template("company_detail.html", form=form, company=company)


@admin_bp.route("/companies/<int:company_id>/commission_rules", methods=["GET", "POST"])
@login_required
@role_required(ROLE_ADMIN)
def commission_rules(company_id):
    company = InsuranceCompany.query.get_or_404(company_id)
    form = CommissionRuleForm()
    if form.validate_on_submit():
        rule = CommissionRule(
            company_id=company.id,
            description=form.description.data,
            commission_percent=form.commission_percent.data,
            is_active=form.is_active.data
        )
        db.session.add(rule)
        db.session.commit()
        flash("Commission rule added.", "success")
        return redirect(url_for("admin.commission_rules", company_id=company.id))

    rules = company.commission_rules.order_by(CommissionRule.created_at.desc()).all()
    return render_template("commission_rules.html", company=company, form=form, rules=rules)


@admin_bp.route("/manual-journal", methods=["GET", "POST"])
@login_required
@role_required(ROLE_ADMIN)
def manual_journal():
    form = ManualJournalForm()
    if form.validate_on_submit():
        entry = ManualJournalEntry(
            description=form.description.data,
            debit_account=form.debit_account.data,
            credit_account=form.credit_account.data,
            amount=form.amount.data,
            created_by=current_user
        )
        db.session.add(entry)
        db.session.commit()
        flash("Journal entry posted.", "success")
        return redirect(url_for("admin.manual_journal"))

    entries = ManualJournalEntry.query.order_by(ManualJournalEntry.date.desc()).limit(50).all()
    return render_template("manual_journal.html", form=form, entries=entries)
