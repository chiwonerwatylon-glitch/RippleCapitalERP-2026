from pathlib import Path

from flask import Flask, render_template, redirect, url_for, flash, request, Blueprint
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from flask_migrate import Migrate
from apscheduler.schedulers.background import BackgroundScheduler

from .config import config_by_name
from .models import (
    db,
    User,
    Policy,
    PremiumTransaction,
    CommissionTransaction,
    InsuranceCompany,
    ROLE_ADMIN,
    ROLE_AGENT,
    ROLE_CLIENT,
)
from .forms import (
    LoginForm,
    RegistrationForm,
    PremiumForm,
    PolicyForm,
    ProfileForm,
    PasswordChangeForm,
)
from .utils import role_required
from .admin import admin_bp
from .email_tasks import send_expiry_reminders

BASE_DIR = Path(__file__).resolve().parent.parent


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

    db.init_app(app)
    Migrate(app, db)
    login_manager.init_app(app)

    # ---------------------------------------------------------------------
    # Register blueprints
    # ---------------------------------------------------------------------
    app.register_blueprint(admin_bp)

    # ---------------------------------------------------------------------
    # Background scheduler for expiry reminders
    # ---------------------------------------------------------------------
    scheduler = BackgroundScheduler(
        timezone=app.config.get("SCHEDULER_TIMEZONE", "UTC")
    )
    scheduler.add_job(
        func=send_expiry_reminders,
        trigger="interval",
        hours=24,
        id="expiry_reminders",
    )
    scheduler.start()

    # Ensure scheduler stops with app
    @app.teardown_appcontext
    def shutdown_session(exception=None):
        db.session.remove()

    # ---------------------------------------------------------------------
    # Blueprints for auth and core
    # ---------------------------------------------------------------------
    auth_bp = Blueprint("auth", __name__)
    core_bp = Blueprint("core", __name__)

    # ====================== AUTH ROUTES ======================

    @auth_bp.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("core.index"))

        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(email=form.email.data.lower()).first()
            if user and user.check_password(form.password.data) and user.is_active:
                login_user(user)
                flash("Logged in successfully.", "success")
                next_page = request.args.get("next")
                return redirect(next_page or url_for("core.index"))
            flash("Invalid credentials or inactive account.", "danger")
        return render_template("login.html", form=form)

    @auth_bp.route("/register", methods=["GET", "POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("core.index"))

        form = RegistrationForm()
        if form.validate_on_submit():
            if User.query.filter_by(email=form.email.data.lower()).first():
                flash("Email already registered.", "warning")
                return render_template("register.html", form=form)
            user = User(
                full_name=form.full_name.data,
                email=form.email.data.lower(),
                phone=form.phone.data,
                role=ROLE_CLIENT,
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
    def index():
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))

        if current_user.role == ROLE_CLIENT:
            return redirect(url_for("core.client_dashboard"))
        elif current_user.role in (ROLE_AGENT, ROLE_ADMIN):
            return redirect(url_for("core.agent_dashboard"))
        return redirect(url_for("auth.login"))

    @core_bp.route("/client/dashboard")
    @login_required
    @role_required(ROLE_CLIENT)
    def client_dashboard():
        policies = current_user.policies.order_by(Policy.start_date.desc()).all()
        return render_template("client_dashboard.html", policies=policies)

    @core_bp.route("/agent/dashboard")
    @login_required
    @role_required(ROLE_AGENT, ROLE_ADMIN)
    def agent_dashboard():
        # Show policies sold by this agent (or all if admin)
        if current_user.role == ROLE_AGENT:
            policies = (
                Policy.query.filter_by(agent_id=current_user.id)
                .order_by(Policy.start_date.desc())
                .all()
            )
        else:
            policies = Policy.query.order_by(Policy.start_date.desc()).all()

        # Basic revenue summary
        total_commission = 0.0
        for p in policies:
            for c in p.commissions:
                total_commission += c.amount

        return render_template(
            "agent_dashboard.html",
            policies=policies,
            total_commission=total_commission,
        )

    @core_bp.route("/policies/new", methods=["GET", "POST"])
    @login_required
    @role_required(ROLE_AGENT, ROLE_ADMIN)
    def policy_create():
        form = PolicyForm()
        # Populate select fields
        clients = (
            User.query.filter_by(role=ROLE_CLIENT).order_by(User.full_name).all()
        )
        companies = InsuranceCompany.query.order_by(InsuranceCompany.name).all()
        form.client_id.choices = [(c.id, c.full_name) for c in clients]
        form.company_id.choices = [(c.id, c.name) for c in companies]

        if form.validate_on_submit():
            policy = Policy(
                policy_number=form.policy_number.data,
                client_id=form.client_id.data,
                agent_id=current_user.id,
                company_id=form.company_id.data,
                product_name=form.product_name.data,
                coverage_amount=form.coverage_amount.data,
                premium_amount=form.premium_amount.data,
                premium_frequency=form.premium_frequency.data,
                start_date=form.start_date.data,
                end_date=form.end_date.data,
            )
            db.session.add(policy)
            db.session.commit()
            flash("Policy created.", "success")
            return redirect(url_for("core.agent_dashboard"))

        return render_template("policy_detail.html", form=form, policy=None)

    @core_bp.route("/policies/<int:policy_id>")
    @login_required
    def policy_view(policy_id):
        policy = Policy.query.get_or_404(policy_id)
        # Access control: clients can only see their own, agents their own/all
        if current_user.role == ROLE_CLIENT and policy.client_id != current_user.id:
            flash("You do not have access to this policy.", "danger")
            return redirect(url_for("core.client_dashboard"))
        if current_user.role == ROLE_AGENT and policy.agent_id != current_user.id:
            flash("You do not have access to this policy.", "danger")
            return redirect(url_for("core.agent_dashboard"))

        premiums = policy.premiums.order_by(
            PremiumTransaction.date_received.desc()
        ).all()
        commissions = policy.commissions.order_by(
            CommissionTransaction.date_earned.desc()
        ).all()

        return render_template(
            "policy_detail.html",
            policy=policy,
            premiums=premiums,
            commissions=commissions,
            form=None,
        )

    @core_bp.route("/policies/<int:policy_id>/premium", methods=["GET", "POST"])
    @login_required
    @role_required(ROLE_AGENT, ROLE_ADMIN)
    def policy_premium_record(policy_id):
        policy = Policy.query.get_or_404(policy_id)
        if current_user.role == ROLE_AGENT and policy.agent_id != current_user.id:
            flash("You do not have access to this policy.", "danger")
            return redirect(url_for("core.agent_dashboard"))

        form = PremiumForm()
        if form.validate_on_submit():
            premium = PremiumTransaction(
                policy_id=policy.id,
                amount=form.amount.data,
                payment_method=form.payment_method.data,
                reference=form.reference.data,
            )
            db.session.add(premium)
            db.session.flush()

            # Commission calculation: use company active rule (if any)
            company = policy.company
            # get the latest active commission rule
            rule = (
                company.commission_rules.filter_by(is_active=True)
                .order_by(db.text("created_at DESC"))
                .first()
            )

            if rule:
                commission_amount = premium.amount * (
                    rule.commission_percent / 100.0
                )
            else:
                commission_amount = 0.0

            if commission_amount > 0:
                commission = CommissionTransaction(
                    policy_id=policy.id,
                    premium_transaction_id=premium.id,
                    agent_id=policy.agent_id,
                    amount=commission_amount,
                    notes=(
                        f"Auto-calculated {rule.commission_percent}% commission."
                        if rule
                        else "Auto-calculated commission."
                    ),
                )
                db.session.add(commission)

            db.session.commit()
            flash("Premium recorded and commission calculated.", "success")
            return redirect(url_for("core.policy_view", policy_id=policy.id))

        return render_template("premium_list.html", policy=policy, form=form)

    # ====================== PROFILE ROUTES ======================

    @core_bp.route("/profile", methods=["GET", "POST"])
    @login_required
    def profile():
        profile_form = ProfileForm(obj=current_user)
        password_form = PasswordChangeForm()

        # Only handle profile update here (POST from profile_form)
        if profile_form.validate_on_submit() and "full_name" in request.form:
            current_user.full_name = profile_form.full_name.data
            current_user.phone = profile_form.phone.data
            db.session.commit()
            flash("Profile updated.", "success")
            return redirect(url_for("core.profile"))

        return render_template(
            "profile.html",
            profile_form=profile_form,
            password_form=password_form,
        )

    @core_bp.route("/profile/change-password", methods=["POST"])
    @login_required
    def profile_change_password():
        profile_form = ProfileForm(obj=current_user)  # for rendering
        password_form = PasswordChangeForm()

        if password_form.validate_on_submit():
            if not current_user.check_password(
                password_form.current_password.data
            ):
                flash("Current password is incorrect.", "danger")
                return render_template(
                    "profile.html",
                    profile_form=profile_form,
                    password_form=password_form,
                )
            current_user.set_password(password_form.new_password.data)
            db.session.commit()
            flash("Password changed successfully.", "success")
            return redirect(url_for("core.profile"))

        # If invalid, show errors
        return render_template(
            "profile.html",
            profile_form=profile_form,
            password_form=password_form,
        )

    # ====================== ERROR HANDLERS ======================

    @core_bp.app_errorhandler(404)
    def page_not_found(e):
        return render_template("404.html"), 404

    app.register_blueprint(core_bp)

    return app
