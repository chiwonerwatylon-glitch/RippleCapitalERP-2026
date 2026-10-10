from pathlib import Path
import os
import re
from datetime import datetime, date
import io

from flask import (
    Flask,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    Blueprint,
    send_file,
    jsonify,
)
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from flask_migrate import Migrate
import click
from werkzeug.utils import secure_filename

# Optional openpyxl support
try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill

    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

from .config import config_by_name
from .models import db, User, ROLE_OWNER, ROLE_ADMIN, ROLE_AGENT, ROLE_CLIENT
from .utils import (
    role_required,
    get_account_owner_id,
    PremiumCalculator,
    generate_policy_number,
    calculate_end_date_from_frequency,
    get_days_in_period,
    MOTOR_PRODUCTS,
    HOMEOWNERS_PRODUCT,
    MOTOR_RATE_RANGE,
    HOMEOWNERS_RATE_RANGE,
)

# Safely import the models
try:
    from .models import (
        Policy,
        PremiumRemittance,
        Claim,
        ClaimDocument,
        Client,
        Company,
        InsuranceProduct,
        CommissionRule,
        ManualJournalEntry,
        BulkUploadLog,
        ROLE_OWNER,
    )

    HAS_NEW_MODELS = True
except ImportError:
    # Fall back to old models if new ones don't exist
    HAS_NEW_MODELS = False
    try:
        from .models import (
            Policy,
            PremiumTransaction,
            CommissionTransaction,
            InsuranceCompany,
        )
    except ImportError:
        pass

from .forms import (
    LoginForm,
    RegistrationForm,
    ProfileForm,
    PasswordChangeForm,
    ForgotPasswordForm,
    ResetPasswordForm,
)
from .email_tasks import (
    send_password_reset_email,
    send_expiry_reminders,
    notify_policy,
    policy_snapshot,
    safe_notify,
)
from .tokens import make_reset_token, verify_reset_token

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_FOLDER = BASE_DIR / "uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message_category = "warning"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


DEFAULT_PRODUCTS = [
    {
        "name": "Motor Comprehensive",
        "coverage_type": "Motor",
        "description": "Covers loss or damage to the insured vehicle and liability to third parties.",
    },
    {
        "name": "Third Party",
        "coverage_type": "Motor",
        "description": "Covers legal liability for injury or damage to third parties caused by the insured vehicle.",
    },
    {
        "name": "Full Third Party",
        "coverage_type": "Motor",
        "description": "Third party liability plus fire and theft cover for the insured vehicle.",
    },
    {
        "name": "Homeowners",
        "coverage_type": "Property",
        "description": "Covers the home structure and permanent fixtures against insured perils.",
    },
    {
        "name": "Household",
        "coverage_type": "Property",
        "description": "Covers household contents and personal belongings against loss or damage.",
    },
    {
        "name": "Business Combined",
        "coverage_type": "General Insurance",
        "description": "Package cover for business property, contents, money and liability.",
    },
    {
        "name": "GIT (Goods in Transit)",
        "coverage_type": "Specialty",
        "description": "Covers goods against loss or damage while being transported.",
    },
    {
        "name": "Agriculture",
        "coverage_type": "Specialty",
        "description": "Covers crops, livestock and farm assets against insured risks.",
    },
    {
        "name": "Asset All Risk",
        "coverage_type": "Property",
        "description": "Broad cover for physical loss or damage to insured assets from any non-excluded cause.",
    },
]


def ensure_user_has_default_products(user):
    """Create the default insurance products for a user if they have none.

    Products are generic (company_id is NULL) so each product type exists
    exactly once per user. Returns the user's list of products.
    """
    account_id = get_account_owner_id(user)
    products = InsuranceProduct.query.filter_by(owner_id=account_id).all()
    if products:
        return products

    for product_data in DEFAULT_PRODUCTS:
        exists = InsuranceProduct.query.filter_by(
            owner_id=account_id,
            company_id=None,
            name=product_data["name"],
        ).first()
        if not exists:
            db.session.add(
                InsuranceProduct(
                    owner_id=account_id,
                    company_id=None,
                    **product_data,
                )
            )

    db.session.commit()
    return InsuranceProduct.query.filter_by(owner_id=account_id).all()


def create_app(config_name=None):
    app = Flask(
        __name__,
        static_folder=str(BASE_DIR / "static"),
        template_folder=str(BASE_DIR / "templates"),
    )

    config_name = config_name or "default"
    app.config.from_object(config_by_name[config_name])
    app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

    db.init_app(app)
    Migrate(app, db)
    login_manager.init_app(app)

    # ====================== JINJA FILTERS ======================
    @app.context_processor
    def inject_globals():
        return {
            "datetime": datetime,
            "date": date,
        }

    # ====================== BLUEPRINTS ======================
    auth_bp = Blueprint("auth", __name__)
    core_bp = Blueprint("core", __name__)

    # ====================== AUTH ROUTES ======================

    @auth_bp.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("core.dashboard"))

        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(email=form.email.data.lower()).first()
            if user and user.check_password(form.password.data) and user.is_active:
                login_user(user)
                flash("Logged in successfully.", "success")
                next_page = request.args.get("next")
                return redirect(next_page or url_for("core.dashboard"))
            flash("Invalid credentials or inactive account.", "danger")
        return render_template("login.html", form=form)

    @auth_bp.route("/register", methods=["GET", "POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("core.dashboard"))

        form = RegistrationForm()
        if form.validate_on_submit():
            if User.query.filter_by(email=form.email.data.lower()).first():
                flash("Email already registered.", "warning")
                return render_template("register.html", form=form)

            if not HAS_NEW_MODELS:
                flash("Registration is not available.", "danger")
                return render_template("register.html", form=form)

            # Only clients already entered by the insurer may register.
            def _normalize_name(value):
                return " ".join((value or "").split()).lower()

            submitted_name = _normalize_name(form.full_name.data)
            unlinked_clients = Client.query.filter(Client.user_id.is_(None)).all()
            matches = [
                c
                for c in unlinked_clients
                if _normalize_name(f"{c.first_name} {c.last_name}") == submitted_name
            ]

            if not matches:
                flash(
                    "Your name is not on record. Please ask your insurer to add you first.",
                    "danger",
                )
                return render_template("register.html", form=form)
            if len(matches) > 1:
                flash(
                    "More than one client record matches your name. "
                    "Please contact your insurer to complete your registration.",
                    "danger",
                )
                return render_template("register.html", form=form)

            client = matches[0]
            try:
                user = User(
                    full_name=form.full_name.data,
                    email=form.email.data.lower(),
                    phone=form.phone.data,
                    role=ROLE_CLIENT,
                    account_owner_id=client.owner_id,
                )
                user.set_password(form.password.data)
                db.session.add(user)
                db.session.flush()
                client.user_id = user.id
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                flash(f"Registration failed: {str(e)}", "danger")
                return render_template("register.html", form=form)

            flash("Registration successful. You can now log in.", "success")
            return redirect(url_for("auth.login"))
        return render_template("register.html", form=form)

    @auth_bp.route("/forgot-password", methods=["GET", "POST"])
    def forgot_password():
        if current_user.is_authenticated:
            return redirect(url_for("core.dashboard"))

        form = ForgotPasswordForm()
        if form.validate_on_submit():
            user = User.query.filter_by(email=form.email.data.lower()).first()
            if user and user.is_active:
                token = make_reset_token(user)
                base = app.config.get("PUBLIC_BASE_URL") or request.host_url.rstrip("/")
                link = f"{base}{url_for('auth.reset_password', token=token)}"
                send_password_reset_email(user, link)
            # Same message whether or not the account exists.
            flash(
                "If an account exists for that email, a reset link has been sent.",
                "info",
            )
            return redirect(url_for("auth.login"))
        return render_template("forgot_password.html", form=form)

    @auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
    def reset_password(token):
        if current_user.is_authenticated:
            return redirect(url_for("core.dashboard"))

        user = verify_reset_token(token)
        if user is None:
            flash("This reset link is invalid or has expired. Please request a new one.", "danger")
            return redirect(url_for("auth.forgot_password"))

        form = ResetPasswordForm()
        if form.validate_on_submit():
            user.set_password(form.password.data)
            db.session.commit()
            flash("Your password has been reset. You can now sign in.", "success")
            return redirect(url_for("auth.login"))
        return render_template("reset_password.html", form=form)

    @auth_bp.route("/logout")
    @login_required
    def logout():
        logout_user()
        flash("You have been logged out.", "info")
        return redirect(url_for("auth.login"))

    app.register_blueprint(auth_bp, url_prefix="/auth")

    # ====================== CORE ROUTES ======================

    def _client_policies():
        """Return the policies of the Client record linked to the current user."""
        client = Client.query.filter_by(user_id=current_user.id).first()
        if client is None:
            return []
        return Policy.query.filter_by(client_id=client.id).all()

    def _client_claims():
        """Return the claims raised against the Client record linked to the current user."""
        client = Client.query.filter_by(user_id=current_user.id).first()
        if client is None:
            return []
        return (
            Claim.query.filter_by(client_id=client.id)
            .order_by(Claim.claim_date.desc())
            .all()
        )

    @core_bp.route("/")
    @core_bp.route("/dashboard")
    @login_required
    def dashboard():
        try:
            if HAS_NEW_MODELS:
                if current_user.role == ROLE_CLIENT:
                    policies = _client_policies()
                    return render_template(
                        "client_dashboard.html", policies=policies, claims=_client_claims()
                    )
                else:
                    owner_id = get_account_owner_id()
                    clients_count = Client.query.filter_by(owner_id=owner_id).count()
                    policies_count = Policy.query.filter_by(owner_id=owner_id).count()
                    companies_count = Company.query.filter_by(
                        owner_id=owner_id
                    ).count()
                    products_count = InsuranceProduct.query.filter_by(
                        owner_id=owner_id
                    ).count()

                    policies = Policy.query.filter_by(owner_id=owner_id).all()
                    total_premiums = (
                        sum(p.total_premiums_paid() for p in policies)
                        if policies
                        else 0
                    )
                    total_commissions = (
                        sum(p.total_commission_earned() for p in policies)
                        if policies
                        else 0
                    )

                    return render_template(
                        "owner_dashboard.html",
                        clients_count=clients_count,
                        policies_count=policies_count,
                        companies_count=companies_count,
                        products_count=products_count,
                        total_premiums=total_premiums,
                        total_commissions=total_commissions,
                        recent_policies=policies[:10],
                    )
            else:
                # Fallback for old schema
                if current_user.role == ROLE_CLIENT:
                    policies = Policy.query.filter_by(
                        client_id=current_user.id
                    ).all()
                    return render_template(
                        "client_dashboard.html", policies=policies, claims=_client_claims()
                    )
                else:
                    policies = Policy.query.all()
                    total_commission = 0.0
                    try:
                        for p in policies:
                            for c in p.commissions:
                                total_commission += c.amount
                    except Exception:
                        pass
                    return render_template(
                        "agent_dashboard.html",
                        policies=policies,
                        total_commission=total_commission,
                    )
        except Exception as e:
            flash(f"Error loading dashboard: {str(e)}", "warning")
            # Render a simple fallback page instead of non-existent index.html
            if current_user.role == ROLE_CLIENT:
                return render_template("client_dashboard.html", policies=[], claims=[])
            else:
                return render_template(
                    "owner_dashboard.html",
                    clients_count=0,
                    policies_count=0,
                    companies_count=0,
                    products_count=0,
                    total_premiums=0,
                    total_commissions=0,
                    recent_policies=[],
                )

    # Alias for backward compatibility
    @core_bp.route("/index")
    @login_required
    def index():
        return redirect(url_for("core.dashboard"))

    @core_bp.route("/clients")
    @login_required
    def clients():
        if HAS_NEW_MODELS:
            clients_list = Client.query.filter_by(
                owner_id=get_account_owner_id()
            ).all()
        else:
            clients_list = []
        return render_template("clients.html", clients=clients_list)

    @core_bp.route("/clients/add", methods=["GET", "POST"])
    @login_required
    def add_client():
        if request.method == "POST" and HAS_NEW_MODELS:
            try:
                client = Client(
                    first_name=request.form.get("first_name"),
                    last_name=request.form.get("last_name"),
                    email=request.form.get("email"),
                    phone=request.form.get("phone"),
                    address=request.form.get("address"),
                    owner_id=get_account_owner_id(),
                )
                db.session.add(client)
                db.session.commit()
                flash("Client added successfully.", "success")
                return redirect(url_for("core.clients"))
            except Exception as e:
                db.session.rollback()
                flash(f"Error adding client: {str(e)}", "danger")
        return render_template("add_client.html")

    def _validate_client_form(form):
        """Validate and normalize client form data. Returns (data, errors)."""
        data = {
            "first_name": (form.get("first_name") or "").strip(),
            "last_name": (form.get("last_name") or "").strip(),
            "email": (form.get("email") or "").strip(),
            "phone": (form.get("phone") or "").strip(),
            "address": (form.get("address") or "").strip(),
        }
        errors = []
        if not data["first_name"]:
            errors.append("First name is required.")
        if not data["last_name"]:
            errors.append("Last name is required.")
        if data["email"] and not re.match(
            r"^[^@\s]+@[^@\s]+\.[^@\s]+$", data["email"]
        ):
            errors.append("Please enter a valid email address.")
        if data["phone"] and not re.match(
            r"^\+?[0-9\s\-().]{6,30}$", data["phone"]
        ):
            errors.append("Please enter a valid phone number.")
        return data, errors

    @core_bp.route("/clients/<int:client_id>/edit", methods=["GET", "POST"])
    @login_required
    def edit_client(client_id):
        if not HAS_NEW_MODELS:
            flash("Client management is not available.", "danger")
            return redirect(url_for("core.clients"))

        client = Client.query.get_or_404(client_id)
        if client.owner_id != get_account_owner_id():
            flash("You don't have permission to edit this client.", "danger")
            return redirect(url_for("core.clients"))

        if request.method == "POST":
            data, errors = _validate_client_form(request.form)
            if errors:
                for error in errors:
                    flash(error, "warning")
                return render_template(
                    "add_client.html",
                    client=client,
                    form_data=data,
                    editing=True,
                )
            try:
                client.first_name = data["first_name"]
                client.last_name = data["last_name"]
                client.email = data["email"] or None
                client.phone = data["phone"] or None
                client.address = data["address"] or None
                db.session.commit()
                flash("Client updated successfully", "success")
                return redirect(url_for("core.clients"))
            except Exception as e:
                db.session.rollback()
                flash(f"Error updating client: {str(e)}", "danger")
                return render_template(
                    "add_client.html",
                    client=client,
                    form_data=data,
                    editing=True,
                )

        form_data = {
            "first_name": client.first_name or "",
            "last_name": client.last_name or "",
            "email": client.email or "",
            "phone": client.phone or "",
            "address": client.address or "",
        }
        return render_template(
            "add_client.html", client=client, form_data=form_data, editing=True
        )

    @core_bp.route("/clients/<int:client_id>/delete", methods=["POST"])
    @login_required
    def delete_client(client_id):
        if not HAS_NEW_MODELS:
            flash("Client management is not available.", "danger")
            return redirect(url_for("core.clients"))

        client = Client.query.get_or_404(client_id)
        if client.owner_id != get_account_owner_id():
            flash("You don't have permission to delete this client.", "danger")
            return redirect(url_for("core.clients"))

        try:
            # If cascades are configured, this is enough:
            db.session.delete(client)
            db.session.commit()
            flash("Client deleted successfully", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Error deleting client: {str(e)}", "danger")
        return redirect(url_for("core.clients"))

    @core_bp.route("/companies")
    @login_required
    def companies():
        if HAS_NEW_MODELS:
            companies_list = Company.query.filter_by(
                owner_id=get_account_owner_id()
            ).all()
        else:
            companies_list = []
        return render_template("companies.html", companies=companies_list)

    @core_bp.route("/companies/add", methods=["GET", "POST"])
    @login_required
    def add_company():
        if not HAS_NEW_MODELS:
            flash("Company management not available.", "warning")
            return redirect(url_for("core.companies"))

        products_list = ensure_user_has_default_products(current_user)

        if request.method == "POST":
            try:
                name = (request.form.get("name") or "").strip()
                contact_email = (request.form.get("contact_email") or "").strip()
                phone = (request.form.get("phone") or "").strip()
                address = (request.form.get("address") or "").strip()
                website = (request.form.get("website") or "").strip() or None
                description = (request.form.get("description") or "").strip() or None

                if not all([name, contact_email, phone, address]):
                    flash("All required fields must be filled.", "danger")
                    return render_template(
                        "add_company_enhanced.html",
                        products=products_list,
                        company=None,
                        existing_commissions=[],
                    )

                company = Company(
                    name=name,
                    contact_email=contact_email,
                    phone=phone,
                    address=address,
                    website=website,
                    description=description,
                    owner_id=get_account_owner_id(),
                )
                db.session.add(company)
                db.session.flush()

                rules_created = 0
                for product in products_list:
                    commission_str = (
                        request.form.get(f"commission_{product.id}") or ""
                    ).strip()
                    if commission_str:
                        try:
                            percent = float(commission_str)
                        except ValueError:
                            continue
                        if 0 <= percent <= 100:
                            db.session.add(
                                CommissionRule(
                                    owner_id=get_account_owner_id(),
                                    company_id=company.id,
                                    product_id=product.id,
                                    commission_percent=round(percent, 2),
                                    is_active=True,
                                )
                            )
                            rules_created += 1

                db.session.commit()
                msg = f"Company '{name}' created successfully"
                if rules_created > 0:
                    msg += f". Commission rules set for {rules_created} products."
                flash(msg, "success")
                return redirect(url_for("core.companies"))

            except Exception as e:
                db.session.rollback()
                flash(f"Error: {str(e)}", "danger")
                return render_template(
                    "add_company_enhanced.html",
                    products=products_list,
                    company=None,
                    existing_commissions=[],
                )

        return render_template(
            "add_company_enhanced.html",
            products=products_list,
            company=None,
            existing_commissions=[],
        )

    @core_bp.route("/companies/<int:company_id>/edit", methods=["GET", "POST"])
    @login_required
    def edit_company(company_id):
        if not HAS_NEW_MODELS:
            flash("Company management not available.", "warning")
            return redirect(url_for("core.companies"))

        company = Company.query.get_or_404(company_id)
        if company.owner_id != get_account_owner_id():
            flash("You don't have permission to edit this company.", "danger")
            return redirect(url_for("core.companies"))

        products_list = ensure_user_has_default_products(current_user)
        existing_commissions = CommissionRule.query.filter_by(
            company_id=company_id, owner_id=get_account_owner_id()
        ).all()

        if request.method == "POST":
            try:
                name = (request.form.get("name") or "").strip()
                contact_email = (request.form.get("contact_email") or "").strip()
                phone = (request.form.get("phone") or "").strip()
                address = (request.form.get("address") or "").strip()

                if not all([name, contact_email, phone, address]):
                    flash("All required fields must be filled.", "danger")
                    return render_template(
                        "add_company_enhanced.html",
                        products=products_list,
                        company=company,
                        existing_commissions=existing_commissions,
                    )

                company.name = name
                company.contact_email = contact_email
                company.phone = phone
                company.address = address
                company.website = (
                    (request.form.get("website") or "").strip() or None
                )
                company.description = (
                    (request.form.get("description") or "").strip() or None
                )

                for product in products_list:
                    commission_str = (
                        request.form.get(f"commission_{product.id}") or ""
                    ).strip()
                    rule = CommissionRule.query.filter_by(
                        company_id=company_id,
                        product_id=product.id,
                        owner_id=get_account_owner_id(),
                    ).first()

                    if commission_str:
                        try:
                            percent = float(commission_str)
                        except ValueError:
                            continue
                        if 0 <= percent <= 100:
                            if rule:
                                rule.commission_percent = round(percent, 2)
                            else:
                                db.session.add(
                                    CommissionRule(
                                        owner_id=get_account_owner_id(),
                                        company_id=company_id,
                                        product_id=product.id,
                                        commission_percent=round(percent, 2),
                                        is_active=True,
                                    )
                                )
                    elif rule:
                        db.session.delete(rule)

                db.session.commit()
                flash("Company updated successfully.", "success")
                return redirect(url_for("core.companies"))

            except Exception as e:
                db.session.rollback()
                flash(f"Error updating company: {str(e)}", "danger")
                return render_template(
                    "add_company_enhanced.html",
                    products=products_list,
                    company=company,
                    existing_commissions=existing_commissions,
                )

        return render_template(
            "add_company_enhanced.html",
            products=products_list,
            company=company,
            existing_commissions=existing_commissions,
        )

    def _rule_form_options():
        """Return (companies, products) available to the current user for rule forms."""
        if not HAS_NEW_MODELS:
            return [], []
        products_list = ensure_user_has_default_products(current_user)
        companies_list = (
            Company.query.filter_by(owner_id=get_account_owner_id())
            .order_by(Company.name)
            .all()
        )
        return companies_list, products_list

    def _validate_rule_form(form, rule_id=None):
        """Validate commission rule form data.

        Returns (data, error). ``data`` is a dict of cleaned values when valid.
        """
        company_raw = (form.get("company_id") or "").strip()
        product_raw = (form.get("product_id") or "").strip()
        percent_raw = (form.get("commission_percent") or "").strip()
        description = (form.get("description") or "").strip()
        is_active = form.get("is_active", "1") == "1"

        if not product_raw:
            return None, "Please select a product."
        if not company_raw:
            return None, "Please select a company."
        if not percent_raw:
            return None, "Please enter a commission percentage."

        try:
            product_id = int(product_raw)
            company_id = int(company_raw)
        except ValueError:
            return None, "Invalid company or product selected."

        try:
            percent = float(percent_raw)
        except ValueError:
            return None, "Commission percentage must be a number."
        if percent != percent or percent < 0 or percent > 100:  # NaN or out of range
            return None, "Commission percentage must be between 0 and 100."

        if len(description) > 255:
            return None, "Description must be 255 characters or fewer."

        product = InsuranceProduct.query.filter_by(
            id=product_id, owner_id=get_account_owner_id()
        ).first()
        if not product:
            return None, "Selected product was not found."
        company = Company.query.filter_by(
            id=company_id, owner_id=get_account_owner_id()
        ).first()
        if not company:
            return None, "Selected company was not found."

        duplicate = CommissionRule.query.filter_by(
            company_id=company_id, product_id=product_id
        )
        if rule_id is not None:
            duplicate = duplicate.filter(CommissionRule.id != rule_id)
        if duplicate.first():
            return (
                None,
                "A commission rule already exists for this product and company.",
            )

        return (
            {
                "company_id": company_id,
                "product_id": product_id,
                "commission_percent": round(percent, 2),
                "description": description or None,
                "is_active": is_active,
            },
            None,
        )

    @core_bp.route("/commission-rules")
    @login_required
    def commission_rules():
        if HAS_NEW_MODELS:
            rules = (
                CommissionRule.query.filter_by(owner_id=get_account_owner_id())
                .order_by(CommissionRule.created_at.desc())
                .all()
            )
        else:
            rules = []
        return render_template("commission_rules.html", rules=rules)

    @core_bp.route("/commission-rules/add", methods=["GET", "POST"])
    @login_required
    def add_commission_rule():
        if not HAS_NEW_MODELS:
            flash("Commission rules are not available.", "danger")
            return redirect(url_for("core.commission_rules"))

        companies_list, products_list = _rule_form_options()

        if request.method == "POST":
            data, error = _validate_rule_form(request.form)
            if error:
                flash(error, "danger")
            else:
                try:
                    rule = CommissionRule(
                        owner_id=get_account_owner_id(), **data
                    )
                    db.session.add(rule)
                    db.session.commit()
                    flash("Commission rule created successfully.", "success")
                    return redirect(url_for("core.commission_rules"))
                except Exception as e:
                    db.session.rollback()
                    flash(f"Error adding commission rule: {str(e)}", "danger")

        return render_template(
            "add_commission_rule.html",
            companies=companies_list,
            products=products_list,
            rule=None,
            form_data=request.form if request.method == "POST" else None,
        )

    @core_bp.route(
        "/commission-rules/<int:rule_id>/edit", methods=["GET", "POST"]
    )
    @login_required
    def edit_commission_rule(rule_id):
        if not HAS_NEW_MODELS:
            flash("Commission rules are not available.", "danger")
            return redirect(url_for("core.commission_rules"))

        rule = CommissionRule.query.get_or_404(rule_id)
        if rule.owner_id != get_account_owner_id():
            flash(
                "You don't have permission to edit this commission rule.",
                "danger",
            )
            return redirect(url_for("core.commission_rules"))

        companies_list, products_list = _rule_form_options()

        if request.method == "POST":
            data, error = _validate_rule_form(request.form, rule_id=rule.id)
            if error:
                flash(error, "danger")
            else:
                try:
                    for key, value in data.items():
                        setattr(rule, key, value)
                    db.session.commit()
                    flash("Commission rule updated successfully.", "success")
                    return redirect(url_for("core.commission_rules"))
                except Exception as e:
                    db.session.rollback()
                    flash(
                        f"Error updating commission rule: {str(e)}", "danger"
                    )

        return render_template(
            "add_commission_rule.html",
            companies=companies_list,
            products=products_list,
            rule=rule,
            form_data=request.form if request.method == "POST" else None,
        )

    @core_bp.route(
        "/commission-rules/<int:rule_id>/delete", methods=["POST"]
    )
    @login_required
    def delete_commission_rule(rule_id):
        if not HAS_NEW_MODELS:
            return redirect(url_for("core.commission_rules"))

        rule = CommissionRule.query.get_or_404(rule_id)
        if rule.owner_id != get_account_owner_id():
            flash(
                "You don't have permission to delete this commission rule.",
                "danger",
            )
            return redirect(url_for("core.commission_rules"))

        try:
            db.session.delete(rule)
            db.session.commit()
            flash("Commission rule deleted successfully.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Error deleting commission rule: {str(e)}", "danger")
        return redirect(url_for("core.commission_rules"))

    @core_bp.route("/policies")
    @login_required
    def policies():
        if HAS_NEW_MODELS:
            if current_user.role == ROLE_CLIENT:
                policies_list = _client_policies()
            else:
                policies_list = Policy.query.filter_by(
                    owner_id=get_account_owner_id()
                ).all()
        else:
            policies_list = []
        return render_template(
            "policies_enhanced.html", policies=policies_list
        )

    def _policies_needing_remittance():
        """Policies of the current account that still have an unpaid premium balance."""
        policies_list = (
            Policy.query.filter_by(owner_id=get_account_owner_id())
            .order_by(Policy.policy_number)
            .all()
        )
        return [p for p in policies_list if p.needs_remittance()]

    @core_bp.route("/premium-remittance")
    @login_required
    def premium_remittance():
        if HAS_NEW_MODELS:
            remittances = PremiumRemittance.query.filter_by(
                owner_id=get_account_owner_id()
            ).order_by(PremiumRemittance.created_at.desc()).all()
            policies_list = _policies_needing_remittance()
        else:
            remittances = []
            policies_list = []
        return render_template(
            "premium_remittance.html",
            remittances=remittances,
            policies=policies_list,
        )

    @core_bp.route("/premium-remittance/add", methods=["GET", "POST"])
    @login_required
    def add_premium_remittance():
        if HAS_NEW_MODELS:
            policies_list = _policies_needing_remittance()
        else:
            policies_list = []

        if request.method == "POST" and HAS_NEW_MODELS:
            try:
                policy_id = request.form.get("policy_id", type=int)
                policy = (
                    Policy.query.filter_by(
                        id=policy_id, owner_id=get_account_owner_id()
                    ).first()
                    if policy_id
                    else None
                )
                if policy is None:
                    flash("Please select a valid policy.", "danger")
                    return render_template(
                        "add_premium_remittance.html", policies=policies_list
                    )

                try:
                    amount = float(request.form.get("amount") or 0)
                except ValueError:
                    amount = 0
                if not amount > 0:  # also rejects NaN
                    flash("Amount must be greater than zero.", "danger")
                    return render_template(
                        "add_premium_remittance.html", policies=policies_list
                    )

                outstanding = policy.outstanding_premium()
                if outstanding <= 0:
                    flash(
                        "This policy has no outstanding premium to remit.",
                        "warning",
                    )
                    return render_template(
                        "add_premium_remittance.html", policies=policies_list
                    )
                if amount > outstanding + 0.005:
                    flash(
                        f"Amount exceeds the outstanding premium of ${outstanding:,.2f}.",
                        "danger",
                    )
                    return render_template(
                        "add_premium_remittance.html", policies=policies_list
                    )

                remittance = PremiumRemittance(
                    policy_id=policy.id,
                    amount=amount,
                    payment_method=request.form.get("payment_method"),
                    reference=request.form.get("reference_number")
                    or request.form.get("reference"),
                    owner_id=get_account_owner_id(),
                )
                db.session.add(remittance)
                db.session.commit()
                safe_notify(notify_policy, policy_snapshot(policy), "payment")
                flash(
                    "Premium remittance recorded successfully.", "success"
                )
                return redirect(url_for("core.premium_remittance"))
            except Exception as e:
                db.session.rollback()
                flash(
                    f"Error recording remittance: {str(e)}", "danger"
                )

        return render_template(
            "add_premium_remittance.html", policies=policies_list
        )

    @core_bp.route("/reports")
    @login_required
    def reports():
        if HAS_NEW_MODELS:
            owner_id = get_account_owner_id()
            clients_count = Client.query.filter_by(owner_id=owner_id).count()
            companies_count = Company.query.filter_by(
                owner_id=owner_id
            ).count()
            policies = Policy.query.filter_by(owner_id=owner_id).all()
            policies_count = len(policies)
            total_premiums = (
                sum(p.total_premiums_paid() for p in policies)
                if policies
                else 0
            )
            total_commissions = (
                sum(p.total_commission_earned() for p in policies)
                if policies
                else 0
            )
            remittances = PremiumRemittance.query.filter_by(
                owner_id=owner_id
            ).all()
        else:
            clients_count = 0
            companies_count = 0
            policies_count = 0
            total_premiums = 0
            total_commissions = 0
            remittances = []

        return render_template(
            "reports.html",
            clients_count=clients_count,
            companies_count=companies_count,
            policies_count=policies_count,
            total_premiums=total_premiums,
            total_commissions=total_commissions,
            remittances_count=len(remittances),
        )

    @core_bp.route("/reports/download/<report_type>")
    @login_required
    def download_report(report_type):
        """Generate and download reports in various formats."""
        if not HAS_NEW_MODELS:
            flash("Reports not available in this version.", "warning")
            return redirect(url_for("core.reports"))

        try:
            owner_id = get_account_owner_id()
            if report_type == "premium-pdf":
                # Generate Premium Report as text file
                policies = Policy.query.filter_by(owner_id=owner_id).all()
                total_premiums = (
                    sum(p.total_premiums_paid() for p in policies)
                    if policies
                    else 0
                )

                filename = (
                    f"Premium_Report_"
                    f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                )
                content = "PREMIUM REPORT\n"
                content += (
                    f"Generated: "
                    f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                )
                content += f"{'=' * 50}\n\n"
                content += (
                    f"Total Premiums Collected: "
                    f"${total_premiums:.2f}\n\n"
                )
                content += "Policy Details:\n"
                content += f"{'-' * 50}\n"

                for policy in policies:
                    content += f"Policy #{policy.policy_number}\n"
                    content += (
                        " Client: "
                        f"{policy.client.full_name() if policy.client else 'N/A'}\n"
                    )
                    content += (
                        f" Amount: "
                        f"${policy.total_premiums_paid():.2f}\n"
                    )
                    content += (
                        f" Premium: "
                        f"${policy.premium_amount:.2f}\n\n"
                    )

                return send_file(
                    io.BytesIO(content.encode()),
                    mimetype="text/plain",
                    as_attachment=True,
                    download_name=filename,
                )

            elif report_type == "commission-pdf":
                # Generate Commission Report as text file
                policies = Policy.query.filter_by(owner_id=owner_id).all()
                total_commissions = (
                    sum(p.total_commission_earned() for p in policies)
                    if policies
                    else 0
                )

                filename = (
                    f"Commission_Report_"
                    f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                )
                content = "COMMISSION REPORT\n"
                content += (
                    f"Generated: "
                    f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                )
                content += f"{'=' * 50}\n\n"
                content += (
                    f"Total Commissions Recorded (after WHT): "
                    f"${total_commissions:.2f}\n\n"
                )
                content += "Commission Details:\n"
                content += f"{'-' * 50}\n"

                for policy in policies:
                    row = policy.commission_breakdown()
                    if row:
                        content += f"Policy #{policy.policy_number}\n"
                        content += (
                            " Client: "
                            f"{policy.client.full_name() if policy.client else 'N/A'}\n"
                        )
                        content += f" Premium base (premium less stamp duty and levy): ${row['base']:.2f}\n"
                        content += f" Commission (gross): ${row['gross']:.2f}\n"
                        content += f" Withholding tax (20%): ${row['withholding_tax']:.2f}\n"
                        content += f" Recorded in books (80%): ${row['recorded']:.2f}\n\n"

                return send_file(
                    io.BytesIO(content.encode()),
                    mimetype="text/plain",
                    as_attachment=True,
                    download_name=filename,
                )

            elif report_type == "clients-excel":
                # Generate Clients Report as CSV
                clients = Client.query.filter_by(owner_id=owner_id).all()

                filename = (
                    f"Clients_Report_"
                    f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                )
                content = "First Name,Last Name,Email,Phone,City,Address\n"

                for client in clients:
                    content += (
                        f"\"{client.first_name}\","
                        f"\"{client.last_name}\","
                        f"\"{client.email or ''}\","
                        f"\"{client.phone or ''}\","
                        f"\"{getattr(client, 'city', '') or ''}\","
                        f"\"{client.address or ''}\"\n"
                    )

                return send_file(
                    io.BytesIO(content.encode()),
                    mimetype="text/csv",
                    as_attachment=True,
                    download_name=filename,
                )

            else:
                flash("Invalid report type.", "warning")
                return redirect(url_for("core.reports"))

        except Exception as e:
            flash(f"Error generating report: {str(e)}", "danger")
            return redirect(url_for("core.reports"))

    @core_bp.route("/profile", methods=["GET", "POST"])
    @login_required
    def profile():
        if request.method == "POST":
            new_email = (
                (request.form.get("email") or current_user.email or "").strip()
            )
            if not new_email:
                flash("Email cannot be empty.", "danger")
                return redirect(url_for("core.profile"))
            if not re.match(
                r"^[^@\s]+@[^@\s]+\.[^@\s]+$", new_email
            ):
                flash("Please enter a valid email address.", "danger")
                return redirect(url_for("core.profile"))
            if new_email.lower() != (current_user.email or "").lower():
                existing = User.query.filter(
                    db.func.lower(User.email) == new_email.lower(),
                    User.id != current_user.id,
                ).first()
                if existing:
                    flash(
                        "That email address is already in use.", "danger"
                    )
                    return redirect(url_for("core.profile"))

            current_user.full_name = request.form.get(
                "full_name", current_user.full_name
            )
            current_user.email = new_email
            current_user.phone = request.form.get(
                "phone", current_user.phone
            )

            if "profile_picture" in request.files:
                file = request.files["profile_picture"]
                if file and file.filename:
                    try:
                        # Validate file extension
                        allowed_extensions = {
                            "png",
                            "jpg",
                            "jpeg",
                            "gif",
                            "webp",
                        }
                        file_ext = (
                            file.filename.rsplit(".", 1)[1].lower()
                            if "." in file.filename
                            else ""
                        )

                        if file_ext not in allowed_extensions:
                            flash(
                                "Invalid file type. Please upload an image.",
                                "warning",
                            )
                        else:
                            filename = secure_filename(
                                f"{current_user.id}_profile_"
                                f"{int(datetime.now().timestamp())}."
                                f"{file_ext}"
                            )
                            filepath = UPLOAD_FOLDER / filename
                            file.save(str(filepath))
                            if HAS_NEW_MODELS and hasattr(
                                current_user, "profile_picture"
                            ):
                                current_user.profile_picture = (
                                    f"/uploads/{filename}"
                                )
                                flash(
                                    "Profile picture updated successfully.",
                                    "success",
                                )
                    except Exception as e:
                        flash(
                            f"Error uploading picture: {str(e)}", "warning"
                        )

            db.session.commit()
            flash("Profile updated successfully.", "success")
            return redirect(url_for("core.profile"))

        profile_picture_url = None
        if (
            HAS_NEW_MODELS
            and hasattr(current_user, "profile_picture")
            and current_user.profile_picture
        ):
            profile_picture_url = current_user.profile_picture

        return render_template(
            "profile.html", profile_picture_url=profile_picture_url
        )

    @core_bp.route("/profile/change-password", methods=["POST"])
    @login_required
    def change_password():
        current_password = request.form.get("current_password")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        if not current_user.check_password(current_password):
            flash("Current password is incorrect.", "danger")
        elif new_password != confirm_password:
            flash("New passwords do not match.", "danger")
        else:
            current_user.set_password(new_password)
            db.session.commit()
            flash("Password changed successfully.", "success")

        return redirect(url_for("core.profile"))

    @core_bp.route("/policies/add", methods=["GET", "POST"])
    @login_required
    def add_policy():
        """Add a new insurance policy with automatic premium calculations."""
        if current_user.role == ROLE_CLIENT:
            flash("Clients cannot create policies.", "warning")
            return redirect(url_for("core.policies"))

        if not HAS_NEW_MODELS:
            flash(
                "Policies feature not available in this version.", "warning"
            )
            return redirect(url_for("core.policies"))

        # Make sure the user has the default products
        ensure_user_has_default_products(current_user)

        # Get account resources for dropdowns (shared across owner/admin/agent)
        account_id = get_account_owner_id()
        clients_list = Client.query.filter_by(owner_id=account_id).all()
        companies_list = Company.query.filter_by(owner_id=account_id).all()
        products_list = InsuranceProduct.query.filter_by(
            owner_id=account_id
        ).all()

        if request.method == "GET":
            if not companies_list:
                flash(
                    "No companies found. Add a company before creating a policy.",
                    "info",
                )
            if not clients_list:
                flash(
                    "No clients found. Add a client before creating a policy.",
                    "info",
                )

        if request.method == "POST":
            try:
                # Get form data
                client_id = (request.form.get("client_id") or "").strip()
                company_id = (request.form.get("company_id") or "").strip()
                product_id = (request.form.get("product_id") or "").strip()
                sum_insured = request.form.get("sum_insured", "0").strip()
                premium_frequency = (
                    request.form.get("premium_frequency", "annual") or "annual"
                )
                start_date_str = (
                    request.form.get("start_date") or ""
                ).strip()
                status = request.form.get("status") or "active"

                # Auto-generate policy number if not provided
                policy_number = (
                    request.form.get("policy_number") or ""
                ).strip()
                if not policy_number:
                    policy_number = generate_policy_number()

                # Validate required fields
                if not all(
                    [client_id, company_id, product_id, sum_insured]
                ):
                    flash(
                        "Client, Company, Product, and Sum Insured are required.",
                        "warning",
                    )
                    return render_template(
                        "add_policy.html",
                        clients=clients_list,
                        companies=companies_list,
                        products=products_list,
                    )

                # Parse sum insured
                try:
                    sum_insured_amount = float(sum_insured)
                except ValueError:
                    flash(
                        "Sum Insured must be a valid number.", "warning"
                    )
                    return render_template(
                        "add_policy.html",
                        clients=clients_list,
                        companies=companies_list,
                        products=products_list,
                    )

                if sum_insured_amount <= 0:
                    flash(
                        "Sum Insured must be greater than 0.", "warning"
                    )
                    return render_template(
                        "add_policy.html",
                        clients=clients_list,
                        companies=companies_list,
                        products=products_list,
                    )

                # Get product name for premium calculation
                product = InsuranceProduct.query.get(int(product_id))
                if not product:
                    flash("Invalid product selected.", "warning")
                    return render_template(
                        "add_policy.html",
                        clients=clients_list,
                        companies=companies_list,
                        products=products_list,
                    )

                # Parse and validate levy
                levy_str = (request.form.get("levy") or "").strip()
                try:
                    levy = float(levy_str) if levy_str else 0.0
                except ValueError:
                    flash(
                        "Levy must be a valid number.", "warning"
                    )
                    return render_template(
                        "add_policy.html",
                        clients=clients_list,
                        companies=companies_list,
                        products=products_list,
                    )

                if levy < 0:
                    flash(
                        "Levy must be a non-negative number.", "warning"
                    )
                    return render_template(
                        "add_policy.html",
                        clients=clients_list,
                        companies=companies_list,
                        products=products_list,
                    )

                # Calculate premium automatically for Motor and Homeowners
                rate = request.form.get("rate", "").strip()
                stamp_duty = request.form.get("stamp_duty", "").strip()
                days_in_period = get_days_in_period(premium_frequency)

                # Motor/Homeowners: user-selected rate within the allowed range
                selected_rate = None
                rate_range = PremiumCalculator.get_rate_range(
                    product.name
                )
                if rate_range is not None:
                    selected_rate_str = (
                        request.form.get("selected_rate") or ""
                    ).strip()
                    try:
                        selected_rate = (
                            float(selected_rate_str)
                            if selected_rate_str
                            else None
                        )
                    except ValueError:
                        selected_rate = None
                    if selected_rate is None:
                        flash(
                            "Please select a rate for this product.",
                            "warning",
                        )
                        return render_template(
                            "add_policy.html",
                            clients=clients_list,
                            companies=companies_list,
                            products=products_list,
                        )
                    if (
                        selected_rate < rate_range["min"]
                        or selected_rate > rate_range["max"]
                    ):
                        flash(
                            f"Rate must be between {rate_range['min']}% and "
                            f"{rate_range['max']}% for {product.name}.",
                            "warning",
                        )
                        return render_template(
                            "add_policy.html",
                            clients=clients_list,
                            companies=companies_list,
                            products=products_list,
                        )

                premium_calc = PremiumCalculator.calculate_premium(
                    product.name,
                    sum_insured_amount,
                    rate=float(rate) if rate else None,
                    stamp_duty_percent=(
                        float(stamp_duty) if stamp_duty else None
                    ),
                    selected_rate=selected_rate,
                    days_in_period=days_in_period,
                )

                if not premium_calc:
                    flash(
                        "Please enter Rate and Stamp Duty percentages for this product.",
                        "warning",
                    )
                    return render_template(
                        "add_policy.html",
                        clients=clients_list,
                        companies=companies_list,
                        products=products_list,
                    )

                # Levy is added on top of the calculated premium
                premium_amount = round(
                    premium_calc["total_premium"] + levy, 2
                )

                # Parse start date (use today if not provided)
                if start_date_str:
                    from datetime import datetime as dt

                    try:
                        start_date = dt.strptime(
                            start_date_str, "%Y-%m-%d"
                        ).date()
                    except ValueError:
                        flash(
                            "Start date must be in YYYY-MM-DD format.",
                            "warning",
                        )
                        return render_template(
                            "add_policy.html",
                            clients=clients_list,
                            companies=companies_list,
                            products=products_list,
                        )
                else:
                    start_date = date.today()

                # Auto-calculate end date based on frequency
                end_date = calculate_end_date_from_frequency(
                    start_date, premium_frequency
                )

                # Check if policy number already exists
                if Policy.query.filter_by(
                    policy_number=policy_number
                ).first():
                    flash(
                        f"Policy number {policy_number} already exists.",
                        "warning",
                    )
                    return render_template(
                        "add_policy.html",
                        clients=clients_list,
                        companies=companies_list,
                        products=products_list,
                    )

                # Create new policy
                policy = Policy(
                    owner_id=account_id,
                    client_id=int(client_id),
                    company_id=int(company_id),
                    product_id=int(product_id),
                    policy_number=policy_number,
                    coverage_amount=sum_insured_amount,
                    premium_amount=premium_amount,
                    levy=levy,
                    stamp_duty=round(premium_calc["stamp_duty"], 2),
                    selected_rate=selected_rate,
                    premium_frequency=premium_frequency,
                    start_date=start_date,
                    end_date=end_date,
                    status=status,
                )

                db.session.add(policy)
                db.session.commit()
                safe_notify(notify_policy, policy_snapshot(policy), "created")
                flash(
                    f"Policy {policy_number} created successfully.",
                    "success",
                )
                return redirect(url_for("core.policies"))

            except Exception as e:
                db.session.rollback()
                flash(f"Error creating policy: {str(e)}", "danger")
                return render_template(
                    "add_policy.html",
                    clients=clients_list,
                    companies=companies_list,
                    products=products_list,
                )

        return render_template(
            "add_policy.html",
            clients=clients_list,
            companies=companies_list,
            products=products_list,
        )

    @core_bp.route("/policies/<int:policy_id>/edit", methods=["GET", "POST"])
    @login_required
    def edit_policy(policy_id):
        """Edit policy number, status and end date; email the client and staff on change."""
        if current_user.role == ROLE_CLIENT:
            flash("Clients cannot edit policies.", "warning")
            return redirect(url_for("core.policies"))

        policy = Policy.query.get_or_404(policy_id)
        if policy.owner_id != get_account_owner_id():
            flash("You don't have permission to edit this policy.", "danger")
            return redirect(url_for("core.policies"))

        allowed_statuses = ["active", "expired", "cancelled"]

        if request.method == "POST":
            new_number = (request.form.get("policy_number") or "").strip()
            new_status = (request.form.get("status") or "").strip()
            end_str = (request.form.get("end_date") or "").strip()

            errors = []
            if not new_number:
                errors.append("Policy number is required.")
            elif new_number != policy.policy_number and Policy.query.filter(
                Policy.policy_number == new_number, Policy.id != policy.id
            ).first():
                errors.append(f"Policy number {new_number} already exists.")
            if new_status not in allowed_statuses:
                errors.append("Invalid status.")
            try:
                new_end = datetime.strptime(end_str, "%Y-%m-%d").date()
            except ValueError:
                errors.append("End date must be a valid date.")
                new_end = None
            if new_end and new_end < policy.start_date:
                errors.append("End date cannot be before the start date.")

            if errors:
                for message in errors:
                    flash(message, "warning")
                return render_template(
                    "policy_edit.html", policy=policy, statuses=allowed_statuses
                )

            changes = []
            if new_number != policy.policy_number:
                changes.append(f"Policy number: {policy.policy_number} -> {new_number}")
            if new_status != policy.status:
                changes.append(f"Status: {policy.status} -> {new_status}")
            if new_end != policy.end_date:
                changes.append(f"End date: {policy.end_date} -> {new_end}")

            if not changes:
                flash("No changes to save.", "info")
                return redirect(url_for("core.view_policy", policy_id=policy.id))

            try:
                policy.policy_number = new_number
                policy.status = new_status
                policy.end_date = new_end
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                flash(f"Error updating policy: {str(e)}", "danger")
                return render_template(
                    "policy_edit.html", policy=policy, statuses=allowed_statuses
                )

            safe_notify(
                notify_policy,
                policy_snapshot(policy),
                "updated",
                note="Changes made:\n- " + "\n- ".join(changes),
            )
            flash(f"Policy {policy.policy_number} updated.", "success")
            return redirect(url_for("core.view_policy", policy_id=policy.id))

        return render_template(
            "policy_edit.html", policy=policy, statuses=allowed_statuses
        )

    # ====================== API ROUTES ======================

    @core_bp.route("/api/calculate-premium", methods=["POST"])
    @login_required
    def calculate_premium_api():
        """API endpoint for real-time premium calculation."""
        try:
            data = request.get_json(silent=True)
            if not data:
                return (
                    jsonify(
                        {
                            "error": "Invalid or missing JSON payload",
                        }
                    ),
                    400,
                )

            product_id = data.get("product_id")
            sum_insured = data.get("sum_insured", 0)
            rate = data.get("rate")
            stamp_duty = data.get("stamp_duty")
            selected_rate = data.get("selected_rate")
            premium_frequency = data.get("premium_frequency")

            try:
                levy = float(data.get("levy") or 0.0)
            except (ValueError, TypeError):
                return jsonify({"error": "Invalid levy"}), 400

            if levy < 0:
                return (
                    jsonify(
                        {
                            "error": "Levy must be a non-negative number",
                        }
                    ),
                    400,
                )

            if not product_id or not sum_insured:
                return (
                    jsonify(
                        {
                            "error": "Missing product_id or sum_insured",
                        }
                    ),
                    400,
                )

            # Get product
            product = InsuranceProduct.query.get(product_id)
            if not product:
                return jsonify({"error": "Product not found"}), 404

            # Calculate premium
            try:
                sum_insured = float(sum_insured)
            except (ValueError, TypeError):
                return jsonify({"error": "Invalid sum_insured"}), 400

            if sum_insured <= 0:
                return (
                    jsonify(
                        {
                            "error": "Sum Insured must be greater than 0",
                        }
                    ),
                    400,
                )

            # Days covered come from the premium frequency
            if premium_frequency:
                days_in_period = get_days_in_period(premium_frequency)
            else:
                try:
                    days_in_period = int(data.get("days_in_period") or 365)
                except (ValueError, TypeError):
                    return (
                        jsonify(
                            {
                                "error": "Invalid days_in_period",
                            }
                        ),
                        400,
                    )

            try:
                selected_rate = (
                    float(selected_rate)
                    if selected_rate not in (None, "")
                    else None
                )
            except (ValueError, TypeError):
                return jsonify({"error": "Invalid selected_rate"}), 400

            rate_range = PremiumCalculator.get_rate_range(product.name)
            if rate_range is not None:
                if selected_rate is None:
                    selected_rate = rate_range["default"]
                if (
                    selected_rate < rate_range["min"]
                    or selected_rate > rate_range["max"]
                ):
                    return (
                        jsonify(
                            {
                                "error": (
                                    "Rate must be between "
                                    f"{rate_range['min']}% and "
                                    f"{rate_range['max']}% for this product"
                                )
                            }
                        ),
                        400,
                    )

            calc = PremiumCalculator.calculate_premium(
                product.name,
                sum_insured,
                rate=float(rate) if rate else None,
                stamp_duty_percent=(
                    float(stamp_duty) if stamp_duty else None
                ),
                selected_rate=selected_rate,
                days_in_period=days_in_period,
            )

            if not calc:
                return (
                    jsonify(
                        {
                            "error": (
                                "Cannot calculate premium for this product. "
                                "Please enter Rate and Stamp Duty."
                            )
                        }
                    ),
                    400,
                )

            calc = dict(calc)
            calc["levy"] = round(levy, 2)
            calc["total_premium"] = round(
                calc["rate_amount"] + calc["stamp_duty"] + levy, 2
            )

            return jsonify(calc)

        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @core_bp.route("/policies/<int:policy_id>/view")
    @login_required
    def view_policy(policy_id):
        """View policy details."""
        if not HAS_NEW_MODELS:
            flash(
                "Policies feature not available in this version.", "warning"
            )
            return redirect(url_for("core.policies"))

        policy = Policy.query.get_or_404(policy_id)

        # Check ownership
        if current_user.role == ROLE_CLIENT:
            allowed = (
                policy.client is not None
                and policy.client.user_id == current_user.id
            )
        else:
            allowed = policy.owner_id == get_account_owner_id()
        if not allowed:
            flash("You don't have permission to view this policy.", "danger")
            return redirect(url_for("core.policies"))

        remittances = PremiumRemittance.query.filter_by(
            policy_id=policy_id
        ).all()
        total_paid = sum(r.amount for r in remittances) if remittances else 0.0
        total_commission = (
            policy.total_commission_earned() if policy else 0.0
        )

        is_client = current_user.role == ROLE_CLIENT
        row = None if is_client else policy.commission_breakdown()
        commissions = []
        if row:
            commissions = [{
                "date_earned": row["date_earned"],
                "amount": row["gross"],
                "notes": (
                    f"Base ${row['base']:,.2f} x {row['rate_percent']}% = ${row['gross']:,.2f}; "
                    f"WHT ${row['withholding_tax']:,.2f}; recorded ${row['recorded']:,.2f}"
                ),
            }]

        return render_template(
            "policy_detail.html",
            policy=policy,
            remittances=remittances,
            premiums=remittances,
            commissions=commissions,
            commission_base=row["base"] if row else 0.0,
            commission_gross=row["gross"] if row else 0.0,
            commission_wht=row["withholding_tax"] if row else 0.0,
            commission_recorded=row["recorded"] if row else 0.0,
            total_paid=total_paid,
            total_commission=total_commission,
            is_client=is_client,
        )

    @core_bp.route("/policies/<int:policy_id>/delete", methods=["POST"])
    @login_required
    def delete_policy(policy_id):
        """Delete a policy (owner only)."""
        if current_user.role == ROLE_CLIENT:
            flash("Clients cannot delete policies.", "warning")
            return redirect(url_for("core.policies"))

        if not HAS_NEW_MODELS:
            flash(
                "Policies feature not available in this version.", "warning"
            )
            return redirect(url_for("core.policies"))

        policy = Policy.query.get_or_404(policy_id)

        # Check ownership
        if policy.owner_id != get_account_owner_id():
            flash(
                "You don't have permission to delete this policy.", "danger"
            )
            return redirect(url_for("core.policies"))

        try:
            policy_number = policy.policy_number
            snapshot = policy_snapshot(policy)
            db.session.delete(policy)
            db.session.commit()
            safe_notify(notify_policy, snapshot, "deleted")
            flash(f"Policy {policy_number} has been deleted.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Error deleting policy: {str(e)}", "danger")

        return redirect(url_for("core.policies"))

    @core_bp.route("/agent-dashboard")
    @login_required
    def agent_dashboard():
        """Alias for owner dashboard (backward compatibility)."""
        return redirect(url_for("core.dashboard"))

    # ====================== CLAIMS ROUTES ======================
    from .claims_routes import register_claims_routes

    register_claims_routes(core_bp)

    # ====================== ERROR HANDLERS ======================

    @core_bp.app_errorhandler(404)
    def page_not_found(e):
        return render_template("404.html"), 404

    @core_bp.app_errorhandler(403)
    def forbidden(e):
        return render_template("403.html"), 403

    app.register_blueprint(core_bp)

    # Register admin blueprint if it exists
    try:
        from .admin import admin_bp

        app.register_blueprint(admin_bp)
    except ImportError:
        pass

    @app.cli.command("send-test-email")
    @click.argument("to_email")
    def send_test_email_command(to_email):
        """Send one live test email through Resend to verify configuration."""
        from .email_tasks import send_email as _send
        ok = _send(to_email, "Ripple Capital ERP: test email", "This is a test email from the ERP.")
        print("Sent." if ok else "NOT sent. Check RESEND_API_KEY and that the sending domain is verified.")

    @app.cli.command("send-expiry-reminders")
    def send_expiry_reminders_command():
        """Email policy-expiry reminders. Schedule once a day."""
        count = send_expiry_reminders()
        print(f"Expiry reminders sent for {count} policies.")

    return app
