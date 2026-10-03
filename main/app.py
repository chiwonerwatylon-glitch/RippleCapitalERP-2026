from pathlib import Path
import os
from datetime import datetime, date
import io

from flask import Flask, render_template, redirect, url_for, flash, request, Blueprint, send_file, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_migrate import Migrate
from werkzeug.utils import secure_filename

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

from .config import config_by_name
from .models import db, User, ROLE_ADMIN, ROLE_CLIENT
from .utils import role_required

# Safely import the models
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
)

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_FOLDER = BASE_DIR / "uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message_category = "warning"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


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
            'datetime': datetime,
            'date': date,
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
            
            role = ROLE_OWNER if HAS_NEW_MODELS else "agent"
            user = User(
                full_name=form.full_name.data,
                email=form.email.data.lower(),
                phone=form.phone.data,
                role=role,
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
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
            if HAS_NEW_MODELS:
                if current_user.role == ROLE_CLIENT:
                    policies = Policy.query.filter_by(client_id=current_user.id).all()
                    return render_template("client_dashboard.html", policies=policies)
                else:
                    clients_count = Client.query.filter_by(owner_id=current_user.id).count()
                    policies_count = Policy.query.filter_by(owner_id=current_user.id).count()
                    companies_count = Company.query.filter_by(owner_id=current_user.id).count()
                    products_count = InsuranceProduct.query.filter_by(owner_id=current_user.id).count()
                    
                    policies = Policy.query.filter_by(owner_id=current_user.id).all()
                    total_premiums = sum(p.total_premiums_paid() for p in policies) if policies else 0
                    total_commissions = sum(p.total_commission_earned() for p in policies) if policies else 0
                    
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
                    policies = Policy.query.filter_by(client_id=current_user.id).all()
                    return render_template("client_dashboard.html", policies=policies)
                else:
                    policies = Policy.query.all()
                    total_commission = 0.0
                    try:
                        for p in policies:
                            for c in p.commissions:
                                total_commission += c.amount
                    except:
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
                return render_template("client_dashboard.html", policies=[])
            else:
                return render_template("owner_dashboard.html", clients_count=0, policies_count=0, companies_count=0, products_count=0, total_premiums=0, total_commissions=0, recent_policies=[])

    # Alias for backward compatibility
    @core_bp.route("/index")
    @login_required
    def index():
        return redirect(url_for("core.dashboard"))

    @core_bp.route("/clients")
    @login_required
    def clients():
        if HAS_NEW_MODELS:
            clients_list = Client.query.filter_by(owner_id=current_user.id).all()
        else:
            clients_list = []
        return render_template("clients.html", clients=clients_list)

    @core_bp.route("/clients/add", methods=["GET", "POST"])
    @login_required
    def add_client():
        if request.method == "POST":
            if HAS_NEW_MODELS:
                try:
                    client = Client(
                        first_name=request.form.get("first_name"),
                        last_name=request.form.get("last_name"),
                        email=request.form.get("email"),
                        phone=request.form.get("phone"),
                        address=request.form.get("address"),
                        owner_id=current_user.id
                    )
                    db.session.add(client)
                    db.session.commit()
                    flash("Client added successfully.", "success")
                    return redirect(url_for("core.clients"))
                except Exception as e:
                    db.session.rollback()
                    flash(f"Error adding client: {str(e)}", "danger")
        return render_template("add_client.html")

    @core_bp.route("/companies")
    @login_required
    def companies():
        if HAS_NEW_MODELS:
            companies_list = Company.query.filter_by(owner_id=current_user.id).all()
        else:
            companies_list = []
        return render_template("companies.html", companies=companies_list)

    @core_bp.route("/companies/add", methods=["GET", "POST"])
    @login_required
    def add_company():
        if request.method == "POST":
            if HAS_NEW_MODELS:
                try:
                    company = Company(
                        name=request.form.get("name"),
                        contact_email=request.form.get("email"),
                        phone=request.form.get("phone"),
                        address=request.form.get("address"),
                        owner_id=current_user.id
                    )
                    db.session.add(company)
                    db.session.commit()
                    flash("Company added successfully.", "success")
                    return redirect(url_for("core.companies"))
                except Exception as e:
                    db.session.rollback()
                    flash(f"Error adding company: {str(e)}", "danger")
        return render_template("add_company.html")

    @core_bp.route("/commission-rules")
    @login_required
    def commission_rules():
        if HAS_NEW_MODELS:
            rules = CommissionRule.query.filter_by(owner_id=current_user.id).all()
        else:
            rules = []
        return render_template("commission_rules.html", rules=rules)

    @core_bp.route("/commission-rules/add", methods=["GET", "POST"])
    @login_required
    def add_commission_rule():
        if HAS_NEW_MODELS:
            companies_list = Company.query.filter_by(owner_id=current_user.id).all()
            products_list = InsuranceProduct.query.filter_by(owner_id=current_user.id).all()
        else:
            companies_list = []
            products_list = []

        if request.method == "POST":
            if HAS_NEW_MODELS:
                try:
                    rule = CommissionRule(
                        company_id=request.form.get("company_id"),
                        product_id=request.form.get("product_id"),
                        commission_percent=float(request.form.get("commission_percent", 0)),
                        owner_id=current_user.id
                    )
                    db.session.add(rule)
                    db.session.commit()
                    flash("Commission rule added successfully.", "success")
                    return redirect(url_for("core.commission_rules"))
                except Exception as e:
                    db.session.rollback()
                    flash(f"Error adding commission rule: {str(e)}", "danger")
        
        return render_template("add_commission_rule.html", companies=companies_list, products=products_list)

    @core_bp.route("/policies")
    @login_required
    def policies():
        if HAS_NEW_MODELS:
            if current_user.role == ROLE_CLIENT:
                policies_list = Policy.query.filter_by(client_id=current_user.id).all()
            else:
                policies_list = Policy.query.filter_by(owner_id=current_user.id).all()
        else:
            policies_list = []
        return render_template("policies.html", policies=policies_list)

    @core_bp.route("/premium-remittance")
    @login_required
    def premium_remittance():
        if HAS_NEW_MODELS:
            remittances = PremiumRemittance.query.filter_by(owner_id=current_user.id).all()
        else:
            remittances = []
        return render_template("premium_remittance.html", remittances=remittances)

    @core_bp.route("/premium-remittance/add", methods=["GET", "POST"])
    @login_required
    def add_premium_remittance():
        if HAS_NEW_MODELS:
            policies_list = Policy.query.filter_by(owner_id=current_user.id).all()
        else:
            policies_list = []

        if request.method == "POST":
            if HAS_NEW_MODELS:
                try:
                    remittance = PremiumRemittance(
                        policy_id=request.form.get("policy_id"),
                        amount=float(request.form.get("amount", 0)),
                        payment_method=request.form.get("payment_method"),
                        reference=request.form.get("reference"),
                        owner_id=current_user.id
                    )
                    db.session.add(remittance)
                    db.session.commit()
                    flash("Premium remittance recorded successfully.", "success")
                    return redirect(url_for("core.premium_remittance"))
                except Exception as e:
                    db.session.rollback()
                    flash(f"Error recording remittance: {str(e)}", "danger")
        
        return render_template("add_premium_remittance.html", policies=policies_list)

    @core_bp.route("/reports")
    @login_required
    def reports():
        if HAS_NEW_MODELS:
            clients_count = Client.query.filter_by(owner_id=current_user.id).count()
            companies_count = Company.query.filter_by(owner_id=current_user.id).count()
            policies = Policy.query.filter_by(owner_id=current_user.id).all()
            policies_count = len(policies)
            total_premiums = sum(p.total_premiums_paid() for p in policies) if policies else 0
            total_commissions = sum(p.total_commission_earned() for p in policies) if policies else 0
            remittances = PremiumRemittance.query.filter_by(owner_id=current_user.id).all()
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
            remittances_count=len(remittances)
        )

    @core_bp.route("/reports/download/<report_type>")
    @login_required
    def download_report(report_type):
        """Generate and download reports in various formats."""
        if not HAS_NEW_MODELS:
            flash("Reports not available in this version.", "warning")
            return redirect(url_for("core.reports"))
        
        try:
            if report_type == "premium-pdf":
                # Generate Premium Report as PDF
                policies = Policy.query.filter_by(owner_id=current_user.id).all()
                total_premiums = sum(p.total_premiums_paid() for p in policies) if policies else 0
                
                filename = f"Premium_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                content = f"PREMIUM REPORT\n"
                content += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                content += f"{'='*50}\n\n"
                content += f"Total Premiums Collected: ${total_premiums:.2f}\n\n"
                content += f"Policy Details:\n"
                content += f"{'-'*50}\n"
                
                for policy in policies:
                    content += f"Policy #{policy.policy_number}\n"
                    content += f"  Client: {policy.client.full_name() if policy.client else 'N/A'}\n"
                    content += f"  Amount: ${policy.total_premiums_paid():.2f}\n"
                    content += f"  Premium: ${policy.premium_amount:.2f}\n\n"
                
                return send_file(
                    io.BytesIO(content.encode()),
                    mimetype="text/plain",
                    as_attachment=True,
                    download_name=filename
                )
            
            elif report_type == "commission-pdf":
                # Generate Commission Report
                policies = Policy.query.filter_by(owner_id=current_user.id).all()
                total_commissions = sum(p.total_commission_earned() for p in policies) if policies else 0
                
                filename = f"Commission_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                content = f"COMMISSION REPORT\n"
                content += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                content += f"{'='*50}\n\n"
                content += f"Total Commissions Earned: ${total_commissions:.2f}\n\n"
                content += f"Commission Details:\n"
                content += f"{'-'*50}\n"
                
                for policy in policies:
                    comm = policy.total_commission_earned()
                    if comm > 0:
                        content += f"Policy #{policy.policy_number}\n"
                        content += f"  Client: {policy.client.full_name() if policy.client else 'N/A'}\n"
                        content += f"  Commission: ${comm:.2f}\n\n"
                
                return send_file(
                    io.BytesIO(content.encode()),
                    mimetype="text/plain",
                    as_attachment=True,
                    download_name=filename
                )
            
            elif report_type == "clients-excel":
                # Generate Clients Report as CSV
                clients = Client.query.filter_by(owner_id=current_user.id).all()
                
                filename = f"Clients_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                content = "First Name,Last Name,Email,Phone,City,Address\n"
                
                for client in clients:
                    content += f"\"{client.first_name}\",\"{client.last_name}\",\"{client.email or ''}\",\"{client.phone or ''}\",\"{client.city or ''}\",\"{client.address or ''}\"\n"
                
                return send_file(
                    io.BytesIO(content.encode()),
                    mimetype="text/csv",
                    as_attachment=True,
                    download_name=filename
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
            current_user.full_name = request.form.get("full_name", current_user.full_name)
            current_user.phone = request.form.get("phone", current_user.phone)
            
            if 'profile_picture' in request.files:
                file = request.files['profile_picture']
                if file and file.filename:
                    try:
                        # Validate file extension
                        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
                        file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
                        
                        if file_ext not in allowed_extensions:
                            flash("Invalid file type. Please upload an image.", "warning")
                        else:
                            filename = secure_filename(f"{current_user.id}_profile_{int(datetime.now().timestamp())}.{file_ext}")
                            filepath = UPLOAD_FOLDER / filename
                            file.save(str(filepath))
                            if HAS_NEW_MODELS and hasattr(current_user, 'profile_picture'):
                                current_user.profile_picture = f"/uploads/{filename}"
                            flash("Profile picture updated successfully.", "success")
                    except Exception as e:
                        flash(f"Error uploading picture: {str(e)}", "warning")
            
            db.session.commit()
            flash("Profile updated successfully.", "success")
            return redirect(url_for("core.profile"))
        
        profile_picture_url = None
        if HAS_NEW_MODELS and hasattr(current_user, 'profile_picture') and current_user.profile_picture:
            profile_picture_url = current_user.profile_picture
        
        return render_template("profile.html", profile_picture_url=profile_picture_url)

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

    return app

