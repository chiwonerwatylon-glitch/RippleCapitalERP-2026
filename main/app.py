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

    @core_bp.route("/clients")
    @login_required
    def clients():
        if HAS_NEW_MODELS:
            clients_list = Client.query.filter_by(owner_id=current_user.id).all()
        else:
            clients_list = []
        return render_template("clients.html", clients=clients_list)

    @core_bp.route("/companies")
    @login_required
    def companies():
        if HAS_NEW_MODELS:
            companies_list = Company.query.filter_by(owner_id=current_user.id).all()
        else:
            companies_list = []
        return render_template("companies.html", companies=companies_list)

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

    @core_bp.route("/reports")
    @login_required
    def reports():
        return render_template("reports.html")

    @core_bp.route("/profile", methods=["GET", "POST"])
    @login_required
    def profile():
        form = ProfileForm()
        if form.validate_on_submit():
            current_user.full_name = form.full_name.data
            current_user.phone = form.phone.data
            
            if form.profile_picture.data:
                try:
                    file = form.profile_picture.data
                    filename = secure_filename(f"{current_user.id}_profile_{datetime.now().timestamp()}.{file.filename.split('.')[-1]}")
                    filepath = UPLOAD_FOLDER / filename
                    file.save(str(filepath))
                    if HAS_NEW_MODELS and hasattr(current_user, 'profile_picture'):
                        current_user.profile_picture = f"/uploads/{filename}"
                except Exception as e:
                    flash(f"Error uploading picture: {str(e)}", "warning")
            
            db.session.commit()
            flash("Profile updated successfully.", "success")
            return redirect(url_for("core.profile"))
        elif request.method == "GET":
            form.full_name.data = current_user.full_name
            form.email.data = current_user.email
            form.phone.data = current_user.phone
        
        return render_template("profile.html", form=form)

    @core_bp.route("/profile/change-password", methods=["POST"])
    @login_required
    def change_password():
        form = PasswordChangeForm()
        if form.validate_on_submit():
            if not current_user.check_password(form.current_password.data):
                flash("Current password is incorrect.", "danger")
            else:
                current_user.set_password(form.new_password.data)
                db.session.commit()
                flash("Password changed successfully.", "success")
                return redirect(url_for("core.profile"))
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

