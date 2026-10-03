from __future__ import annotations

import io
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from flask import (
    Flask,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    Blueprint,
    send_file,
)
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from flask_migrate import Migrate
from werkzeug.utils import secure_filename

# Optional dependency: openpyxl
try:
    import openpyxl  # noqa: F401
    from openpyxl.styles import Font, PatternFill  # noqa: F401

    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

from .config import config_by_name
from .models import db, User, ROLE_ADMIN, ROLE_CLIENT  # noqa: F401
from .utils import role_required  # noqa: F401

# Safely import the "new" model set
try:
    from .models import (
        Policy,
        PremiumRemittance,
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
    HAS_NEW_MODELS = False
    # Fallback to old models if new ones don't exist
    try:
        from .models import (
            Policy,
            PremiumTransaction,
            CommissionTransaction,
            InsuranceCompany,
        )
    except ImportError:
        # Old models not present either; routes depending on them will gracefully degrade
        Policy = None  # type: ignore[name-defined]
        PremiumTransaction = None  # type: ignore[name-defined]
        CommissionTransaction = None  # type: ignore[name-defined]
        InsuranceCompany = None  # type: ignore[name-defined]

# Forms
from .forms import (
    LoginForm,
    RegistrationForm,
    ProfileForm,
    PasswordChangeForm,
)

# === Paths & Uploads ===
BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_FOLDER = BASE_DIR / "uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)

# === Login Manager ===
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message_category = "warning"

# === Logger ===
logger = logging.getLogger(__name__)


@login_manager.user_loader
def load_user(user_id: str) -> Optional[User]:
    if not user_id:
        return None
    try:
        return User.query.get(int(user_id))
    except Exception as e:
        # Log instead of raising to avoid breaking login manager
        logger.exception("Error loading user %s: %s", user_id, e)
        return None


def create_app(config_name: Optional[str] = None) -> Flask:
    """Application factory."""
    app = Flask(
        __name__,
        static_folder=str(BASE_DIR / "static"),
        template_folder=str(BASE_DIR / "templates"),
    )

    # === Configuration ===
    config_name = config_name or os.getenv("FLASK_CONFIG", "default")
    if config_name not in config_by_name:
        raise RuntimeError(f"Invalid config name: {config_name}")
    app.config.from_object(config_by_name[config_name])

    # Uploads
    app.config.setdefault("UPLOAD_FOLDER", str(UPLOAD_FOLDER))
    app.config.setdefault("MAX_CONTENT_LENGTH", 16 * 1024 * 1024)  # 16MB limit

    # === Extensions ===
    db.init_app(app)
    Migrate(app, db)
    login_manager.init_app(app)

    # === Blueprints ===
    auth_bp = Blueprint("auth", __name__)
    core_bp = Blueprint("core", __name__)

    # ====================== AUTH ROUTES ======================

    @auth_bp.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("core.dashboard"))

        form = LoginForm()
        if form.validate_on_submit():
            email = (form.email.data or "").strip().lower()
            password = form.password.data or ""
            user = User.query.filter_by(email=email).first()

            if not user:
                flash("Invalid credentials.", "danger")
                return render_template("login.html", form=form)

            if not user.is_active:
                flash("Account is inactive. Contact support.", "danger")
                return render_template("login.html", form=form)

            if user.check_password(password):
                login_user(user, remember=form.remember_me.data if hasattr(form, "remember_me") else False)
                flash("Logged in successfully.", "success")
                next_page = request.args.get("next")
                # Basic open redirect protection
                if next_page and not next_page.startswith("/"):
                    next_page = url_for("core.dashboard")
                return redirect(next_page or url_for("core.dashboard"))

            flash("Invalid credentials.", "danger")
        return render_template("login.html", form=form)

    @auth_bp.route("/register", methods=["GET", "POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("core.dashboard"))

        form = RegistrationForm()
        if form.validate_on_submit():
            email = (form.email.data or "").strip().lower()
            if User.query.filter_by(email=email).first():
                flash("Email already registered.", "warning")
                return render_template("register.html", form=form)

            # If new models exist, default new user to OWNER. Else "agent".
            role = ROLE_OWNER if HAS_NEW_MODELS else "agent"

            user = User(
                full_name=form.full_name.data.strip(),
                email=email,
                phone=(form.phone.data or "").strip(),
                role=role,
            )
            user.set_password(form.password.data)

            try:
                db.session.add(user)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.exception("Error registering user: %s", e)
                flash("Unexpected error during registration. Please try again.", "danger")
                return render_template("register.html", form=form)

            flash("Registration successful. You can now log in.", "success")
            return redirect(url_for("auth.login"))
        return render_template("register.html", form=form)

    @auth_bp.route("/logout")
    @login_required
    def logout():
        logout_user()
        flash("You have been logged out.", "info")
        return redirect(url_for("auth.login"))

    app.register_blueprint(auth_bp, url_prefix="/auth")

    # ====================== CORE ROUTES ======================

    @core_bp.route("/")
    @core_bp.route("/dashboard")
    @login_required
    def dashboard():
        try:
            # New schema
            if HAS_NEW_MODELS and Policy is not None:
                if current_user.role == ROLE_CLIENT:
                    policies = Policy.query.filter_by(client_id=current_user.id).all()
                    return render_template("client_dashboard.html", policies=policies)

                # Owner / Agent dashboard
                owner_filter = {"owner_id": current_user.id}
                clients_count = Client.query.filter_by(**owner_filter).count()
                policies_qs = Policy.query.filter_by(**owner_filter)
                companies_count = Company.query.filter_by(**owner_filter).count()
                products_count = InsuranceProduct.query.filter_by(**owner_filter).count()

                policies = policies_qs.all()
                total_premiums = sum(
                    (p.total_premiums_paid() or 0.0) for p in policies
                ) if policies else 0.0
                total_commissions = sum(
                    (p.total_commission_earned() or 0.0) for p in policies
                ) if policies else 0.0

                return render_template(
                    "owner_dashboard.html",
                    clients_count=clients_count,
                    policies_count=len(policies),
                    companies_count=companies_count,
                    products_count=products_count,
                    total_premiums=total_premiums,
                    total_commissions=total_commissions,
                    recent_policies=policies[:10],
                )

            # Fallback for old schema
            if current_user.role == ROLE_CLIENT and Policy is not None:
                policies = Policy.query.filter_by(client_id=current_user.id).all()
                return render_template("client_dashboard.html", policies=policies)

            # Agent dashboard (legacy)
            policies = Policy.query.all() if Policy is not None else []
            total_commission = 0.0
            for p in policies:
                # Defensive: some older schemas may not have "commissions" relationship
                commissions = getattr(p, "commissions", []) or []
                for c in commissions:
                    total_commission += getattr(c, "amount", 0.0) or 0.0

            return render_template(
                "agent_dashboard.html",
                policies=policies,
                total_commission=total_commission,
            )

        except Exception as e:
            logger.exception("Error loading dashboard: %s", e)
            flash("Error loading dashboard. Showing a minimal view.", "warning")
            # Render a simple fallback page instead of non-existent index.html
            if current_user.role == ROLE_CLIENT:
                return render_template("client_dashboard.html", policies=[])
            # Default fallback for owner/agent
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

    # ---- Clients ----
    @core_bp.route("/clients")
    @login_required
    def clients():
        if not HAS_NEW_MODELS:
            flash("Client management not available in this version.", "warning")
            return render_template("clients.html", clients=[])
        clients_list = Client.query.filter_by(owner_id=current_user.id).all()
        return render_template("clients.html", clients=clients_list)

    @core_bp.route("/clients/add", methods=["GET", "POST"])
    @login_required
    def add_client():
        if not HAS_NEW_MODELS:
            flash("Client management not available in this version.", "warning")
            return redirect(url_for("core.clients"))

        if request.method == "POST":
            first_name = (request.form.get("first_name") or "").strip()
            last_name = (request.form.get("last_name") or "").strip()
            email = (request.form.get("email") or "").strip() or None
            phone = (request.form.get("phone") or "").strip() or None
            address = (request.form.get("address") or "").strip() or None

            if not first_name or not last_name:
                flash("First name and last name are required.", "warning")
                return render_template("add_client.html")

            client = Client(
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone=phone,
                address=address,
                owner_id=current_user.id,
            )
            try:
                db.session.add(client)
                db.session.commit()
                flash("Client added successfully.", "success")
                return redirect(url_for("core.clients"))
            except Exception as e:
                db.session.rollback()
                logger.exception("Error adding client: %s", e)
                flash("Error adding client. Please try again.", "danger")

        return render_template("add_client.html")

    # ---- Companies ----
    @core_bp.route("/companies")
    @login_required
    def companies():
        if not HAS_NEW_MODELS:
            flash("Company management not available in this version.", "warning")
            return render_template("companies.html", companies=[])

        companies_list = Company.query.filter_by(owner_id=current_user.id).all()
        return render_template("companies.html", companies=companies_list)

    @core_bp.route("/companies/add", methods=["GET", "POST"])
    @login_required
    def add_company():
        if not HAS_NEW_MODELS:
            flash("Company management not available in this version.", "warning")
            return redirect(url_for("core.companies"))

        if request.method == "POST":
            name = (request.form.get("name") or "").strip()
            contact_email = (request.form.get("email") or "").strip() or None
            phone = (request.form.get("phone") or "").strip() or None
            address = (request.form.get("address") or "").strip() or None

            if not name:
                flash("Company name is required.", "warning")
                return render_template("add_company.html")

            company = Company(
                name=name,
                contact_email=contact_email,
                phone=phone,
                address=address,
                owner_id=current_user.id,
            )
            try:
                db.session.add(company)
                db.session.commit()
                flash("Company added successfully.", "success")
                return redirect(url_for("core.companies"))
            except Exception as e:
                db.session.rollback()
                logger.exception("Error adding company: %s", e)
                flash("Error adding company. Please try again.", "danger")

        return render_template("add_company.html")

    # ---- Commission Rules ----
    @core_bp.route("/commission-rules")
    @login_required
    def commission_rules():
        if not HAS_NEW_MODELS:
            flash("Commission rules not available in this version.", "warning")
            return render_template("commission_rules.html", rules=[])
        rules = CommissionRule.query.filter_by(owner_id=current_user.id).all()
        return render_template("commission_rules.html", rules=rules)

    @core_bp.route("/commission-rules/add", methods=["GET", "POST"])
    @login_required
    def add_commission_rule():
        if not HAS_NEW_MODELS:
            flash("Commission rules not available in this version.", "warning")
            return redirect(url_for("core.commission_rules"))

        companies_list = Company.query.filter_by(owner_id=current_user.id).all()
        products_list = InsuranceProduct.query.filter_by(owner_id=current_user.id).all()

        if request.method == "POST":
            try:
                company_id = request.form.get("company_id")
                product_id = request.form.get("product_id")
                commission_percent_str = request.form.get("commission_percent", "0").strip()
                try:
                    commission_percent = float(commission_percent_str)
                except ValueError:
                    flash("Commission percent must be a number.", "warning")
                    return render_template(
                        "add_commission_rule.html",
                        companies=companies_list,
                        products=products_list,
                    )

                if not company_id or not product_id:
                    flash("Company and product are required.", "warning")
                    return render_template(
                        "add_commission_rule.html",
                        companies=companies_list,
                        products=products_list,
                    )

                rule = CommissionRule(
                    company_id=company_id,
                    product_id=product_id,
                    commission_percent=commission_percent,
                    owner_id=current_user.id,
                )
                db.session.add(rule)
                db.session.commit()
                flash("Commission rule added successfully.", "success")
                return redirect(url_for("core.commission_rules"))
            except Exception as e:
                db.session.rollback()
                logger.exception("Error adding commission rule: %s", e)
                flash("Error adding commission rule. Please try again.", "danger")

        return render_template(
            "add_commission_rule.html",
            companies=companies_list,
            products=products_list,
        )

    # ---- Policies ----
    @core_bp.route("/policies")
    @login_required
    def policies():
        if not HAS_NEW_MODELS or Policy is None:
            flash("Policies not available in this version.", "warning")
            return render_template("policies.html", policies=[])

        if current_user.role == ROLE_CLIENT:
            policies_list = Policy.query.filter_by(client_id=current_user.id).all()
        else:
            policies_list = Policy.query.filter_by(owner_id=current_user.id).all()
        return render_template("policies.html", policies=policies_list)

    # ---- Premium Remittance ----
    @core_bp.route("/premium-remittance")
    @login_required
    def premium_remittance():
        if not HAS_NEW_MODELS:
            flash("Premium remittance not available in this version.", "warning")
            return render_template("premium_remittance.html", remittances=[])
        remittances = PremiumRemittance.query.filter_by(owner_id=current_user.id).all()
        return render_template("premium_remittance.html", remittances=remittances)

    @core_bp.route("/premium-remittance/add", methods=["GET", "POST"])
    @login_required
    def add_premium_remittance():
        if not HAS_NEW_MODELS or Policy is None:
            flash("Premium remittance not available in this version.", "warning")
            return redirect(url_for("core.premium_remittance"))

        policies_list = Policy.query.filter_by(owner_id=current_user.id).all()

        if request.method == "POST":
            try:
                policy_id = request.form.get("policy_id")
                if not policy_id:
                    flash("Policy is required.", "warning")
                    return render_template("add_premium_remittance.html", policies=policies_list)

                amount_str = request.form.get("amount", "0").strip()
                try:
                    amount = float(amount_str)
                except ValueError:
                    flash("Amount must be a valid number.", "warning")
                    return render_template("add_premium_remittance.html", policies=policies_list)

                payment_method = (request.form.get("payment_method") or "").strip()
                reference = (request.form.get("reference") or "").strip()

                remittance = PremiumRemittance(
                    policy_id=policy_id,
                    amount=amount,
                    payment_method=payment_method,
                    reference=reference,
                    owner_id=current_user.id,
                )
                db.session.add(remittance)
                db.session.commit()
                flash("Premium remittance recorded successfully.", "success")
                return redirect(url_for("core.premium_remittance"))
            except Exception as e:
                db.session.rollback()
                logger.exception("Error recording premium remittance: %s", e)
                flash("Error recording remittance. Please try again.", "danger")

        return render_template("add_premium_remittance.html", policies=policies_list)

    # ---- Reports ----
    @core_bp.route("/reports")
    @login_required
    def reports():
        if not HAS_NEW_MODELS or Policy is None:
            flash("Reports not available in this version.", "warning")
            return render_template(
                "reports.html",
                clients_count=0,
                companies_count=0,
                policies_count=0,
                total_premiums=0,
                total_commissions=0,
                remittances_count=0,
            )

        owner_filter = {"owner_id": current_user.id}
        clients_count = Client.query.filter_by(**owner_filter).count()
        companies_count = Company.query.filter_by(**owner_filter).count()
        policies = Policy.query.filter_by(**owner_filter).all()

        policies_count = len(policies)
        total_premiums = sum(
            (p.total_premiums_paid() or 0.0) for p in policies
        ) if policies else 0.0
        total_commissions = sum(
            (p.total_commission_earned() or 0.0) for p in policies
        ) if policies else 0.0
        remittances = PremiumRemittance.query.filter_by(**owner_filter).all()

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
    def download_report(report_type: str):
        """Generate and download reports.

        Currently generates text-based 'PDF-like' reports (txt)
        and CSV for clients. Can be extended to true PDFs later.
        """
        if not HAS_NEW_MODELS or Policy is None:
            flash("Reports not available in this version.", "warning")
            return redirect(url_for("core.reports"))

        try:
            now_str = datetime.now().strftime("%Y%m%d_%H%M%S")

            # ---- Premium Report (text) ----
            if report_type == "premium-pdf":
                policies = Policy.query.filter_by(owner_id=current_user.id).all()
                total_premiums = sum(
                    (p.total_premiums_paid() or 0.0) for p in policies
                ) if policies else 0.0

                filename = f"Premium_Report_{now_str}.txt"
                lines = []
                lines.append("PREMIUM REPORT")
                lines.append(f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}")
                lines.append("=" * 50)
                lines.append("")
                lines.append(f"Total Premiums Collected: ${total_premiums:,.2f}")
                lines.append("")
                lines.append("Policy Details:")
                lines.append("-" * 50)

                for policy in policies:
                    client_name = (
                        policy.client.full_name()
                        if getattr(policy, "client", None) is not None
                        else "N/A"
                    )
                    amount_paid = policy.total_premiums_paid() or 0.0
                    premium_amount = getattr(policy, "premium_amount", 0.0) or 0.0
                    lines.append(f"Policy #{policy.policy_number}")
                    lines.append(f"  Client: {client_name}")
                    lines.append(f"  Amount Paid: ${amount_paid:,.2f}")
                    lines.append(f"  Premium: ${premium_amount:,.2f}")
                    lines.append("")

                content = "\n".join(lines).encode("utf-8")
                return send_file(
                    io.BytesIO(content),
                    mimetype="text/plain",
                    as_attachment=True,
                    download_name=filename,
                )

            # ---- Commission Report (text) ----
            if report_type == "commission-pdf":
                policies = Policy.query.filter_by(owner_id=current_user.id).all()
                total_commissions = sum(
                    (p.total_commission_earned() or 0.0) for p in policies
                ) if policies else 0.0

                filename = f"Commission_Report_{now_str}.txt"
                lines = []
                lines.append("COMMISSION REPORT")
                lines.append(f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}")
                lines.append("=" * 50)
                lines.append("")
                lines.append(f"Total Commissions Earned: ${total_commissions:,.2f}")
                lines.append("")
                lines.append("Commission Details:")
                lines.append("-" * 50)

                for policy in policies:
                    comm = policy.total_commission_earned() or 0.0
                    if comm <= 0:
                        continue
                    client_name = (
                        policy.client.full_name()
                        if getattr(policy, "client", None) is not None
                        else "N/A"
                    )
                    lines.append(f"Policy #{policy.policy_number}")
                    lines.append(f"  Client: {client_name}")
                    lines.append(f"  Commission: ${comm:,.2f}")
                    lines.append("")

                content = "\n".join(lines).encode("utf-8")
                return send_file(
                    io.BytesIO(content),
                    mimetype="text/plain",
                    as_attachment=True,
                    download_name=filename,
                )

            # ---- Clients Report (CSV) ----
            if report_type == "clients-excel":
                clients = Client.query.filter_by(owner_id=current_user.id).all()
                filename = f"Clients_Report_{now_str}.csv"

                lines = []
                header = [
                    "First Name",
                    "Last Name",
                    "Email",
                    "Phone",
                    "City",
                    "Address",
                ]
                lines.append(",".join(header))

                def csv_escape(value: Optional[str]) -> str:
                    v = (value or "").replace('"', '""')
                    return f'"{v}"'

                for client in clients:
                    # Assumes Client has city and address; adjust if fields differ
                    row = [
                        csv_escape(client.first_name),
                        csv_escape(client.last_name),
                        csv_escape(getattr(client, "email", "")),
                        csv_escape(getattr(client, "phone", "")),
                        csv_escape(getattr(client, "city", "")),
                        csv_escape(getattr(client, "address", "")),
                    ]
                    lines.append(",".join(row))

                content = "\n".join(lines).encode("utf-8")
                return send_file(
                    io.BytesIO(content),
                    mimetype="text/csv",
                    as_attachment=True,
                    download_name=filename,
                )

            flash("Invalid report type.", "warning")
            return redirect(url_for("core.reports"))

        except Exception as e:
            logger.exception("Error generating report %s: %s", report_type, e)
            flash("Error generating report. Please try again.", "danger")
            return redirect(url_for("core.reports"))

    # ---- Profile ----
    @core_bp.route("/profile", methods=["GET", "POST"])
    @login_required
    def profile():
        # If you're using WTForms, you can replace this manual handling
        # with ProfileForm for better validation.
        if request.method == "POST":
            try:
                full_name = (request.form.get("full_name") or "").strip()
                phone = (request.form.get("phone") or "").strip()

                if full_name:
                    current_user.full_name = full_name
                if phone:
                    current_user.phone = phone

                # Profile picture upload
                if "profile_picture" in request.files:
                    file = request.files["profile_picture"]
                    if file and file.filename:
                        allowed_extensions = {"png", "jpg", "jpeg", "gif", "webp"}
                        ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
                        if ext not in allowed_extensions:
                            flash("Invalid file type. Please upload an image.", "warning")
                        else:
                            safe_name = secure_filename(
                                f"{current_user.id}_profile_{int(datetime.now().timestamp())}.{ext}"
                            )
                            filepath = UPLOAD_FOLDER / safe_name
                            file.save(str(filepath))

                            # Assuming your User model has a profile_picture field
                            if HAS_NEW_MODELS and hasattr(current_user, "profile_picture"):
                                current_user.profile_picture = f"/uploads/{safe_name}"
                            flash("Profile picture updated successfully.", "success")

                db.session.commit()
                flash("Profile updated successfully.", "success")
            except Exception as e:
                db.session.rollback()
                logger.exception("Error updating profile: %s", e)
                flash("Error updating profile. Please try again.", "danger")

            return redirect(url_for("core.profile"))

        profile_picture_url = None
        if HAS_NEW_MODELS and hasattr(current_user, "profile_picture"):
            profile_picture_url = current_user.profile_picture

        return render_template("profile.html", profile_picture_url=profile_picture_url)

    @core_bp.route("/profile/change-password", methods=["POST"])
    @login_required
    def change_password():
        current_password = request.form.get("current_password") or ""
        new_password = request.form.get("new_password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        if not current_user.check_password(current_password):
            flash("Current password is incorrect.", "danger")
        elif not new_password:
            flash("New password cannot be empty.", "danger")
        elif new_password != confirm_password:
            flash("New passwords do not match.", "danger")
        else:
            try:
                current_user.set_password(new_password)
                db.session.commit()
                flash("Password changed successfully.", "success")
            except Exception as e:
                db.session.rollback()
                logger.exception("Error changing password: %s", e)
                flash("Error changing password. Please try again.", "danger")

        return redirect(url_for("core.profile"))

    # ====================== ERROR HANDLERS ======================

    @core_bp.app_errorhandler(404)
    def page_not_found(e):
        logger.warning("404 Not Found: %s", request.path)
        return render_template("404.html"), 404

    @core_bp.app_errorhandler(403)
    def forbidden(e):
        logger.warning("403 Forbidden: %s", request.path)
        return render_template("403.html"), 403

    @core_bp.app_errorhandler(500)
    def internal_server_error(e):
        logger.exception("500 Internal Server Error: %s", e)
        return render_template("500.html"), 500

    app.register_blueprint(core_bp)

    # Register admin blueprint if it exists
    try:
        from .admin import admin_bp

        app.register_blueprint(admin_bp)
    except ImportError:
        logger.info("Admin blueprint not found; skipping admin registration.")

    # Optionally serve uploaded files (for development; in production use a real web server)
    from werkzeug.middleware.shared_data import SharedDataMiddleware

    if not app.debug and not app.testing:
        # In production, typically use nginx or similar to serve /uploads.
        pass
    else:
        # Dev only: serve /uploads
        app.wsgi_app = SharedDataMiddleware(
            app.wsgi_app,
            {
                "/uploads": str(UPLOAD_FOLDER),
            },
        )

    return app
