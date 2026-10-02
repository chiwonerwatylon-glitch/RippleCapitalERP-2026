from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    PasswordField,
    SubmitField,
    FloatField,
    DateField,
    SelectField,
    TextAreaField,
    BooleanField,
)
from wtforms.validators import (
    DataRequired,
    Email,
    Length,
    EqualTo,
    Optional,
    NumberRange,
)


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")


class RegistrationForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    phone = StringField("Phone", validators=[Optional(), Length(max=30)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[DataRequired(), EqualTo("password")],
    )
    submit = SubmitField("Register as Client")


class CompanyForm(FlaskForm):
    name = StringField("Company Name", validators=[DataRequired(), Length(max=150)])
    contact_email = StringField(
        "Contact Email", validators=[Optional(), Email(), Length(max=120)]
    )
    phone = StringField("Phone", validators=[Optional(), Length(max=50)])
    address = StringField("Address", validators=[Optional(), Length(max=255)])
    submit = SubmitField("Save Company")


class CommissionRuleForm(FlaskForm):
    description = StringField("Description", validators=[Optional(), Length(max=255)])
    commission_percent = FloatField(
        "Commission Percent",
        validators=[DataRequired(), NumberRange(min=0, max=100)],
    )
    is_active = BooleanField("Active", default=True)
    submit = SubmitField("Save Rule")


class PolicyForm(FlaskForm):
    policy_number = StringField(
        "Policy Number", validators=[DataRequired(), Length(max=100)]
    )
    client_id = SelectField("Client", coerce=int, validators=[DataRequired()])
    company_id = SelectField(
        "Insurance Company", coerce=int, validators=[DataRequired()]
    )
    product_name = StringField(
        "Product Name", validators=[DataRequired(), Length(max=150)]
    )
    coverage_amount = FloatField("Coverage Amount", validators=[DataRequired()])
    premium_amount = FloatField("Premium Amount", validators=[DataRequired()])
    premium_frequency = SelectField(
        "Premium Frequency",
        choices=[("monthly", "Monthly"), ("quarterly", "Quarterly"), ("annual", "Annual")],
        validators=[DataRequired()],
    )
    start_date = DateField(
        "Start Date", validators=[DataRequired()], format="%Y-%m-%d"
    )
    end_date = DateField("End Date", validators=[DataRequired()], format="%Y-%m-%d")
    submit = SubmitField("Save Policy")


class PremiumForm(FlaskForm):
    amount = FloatField("Amount", validators=[DataRequired(), NumberRange(min=0)])
    payment_method = StringField(
        "Payment Method", validators=[Optional(), Length(max=50)]
    )
    reference = StringField("Reference", validators=[Optional(), Length(max=120)])
    submit = SubmitField("Record Premium")


class ManualJournalForm(FlaskForm):
    description = StringField(
        "Description", validators=[DataRequired(), Length(max=255)]
    )
    debit_account = StringField(
        "Debit Account", validators=[DataRequired(), Length(max=100)]
    )
    credit_account = StringField(
        "Credit Account", validators=[DataRequired(), Length(max=100)]
    )
    amount = FloatField("Amount", validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField("Post Entry")


class ProfileForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired(), Length(max=120)])
    phone = StringField("Phone", validators=[Optional(), Length(max=30)])
    submit = SubmitField("Update Profile")


class PasswordChangeForm(FlaskForm):
    current_password = PasswordField(
        "Current Password", validators=[DataRequired()]
    )
    new_password = PasswordField(
        "New Password", validators=[DataRequired(), Length(min=8)]
    )
    confirm_new_password = PasswordField(
        "Confirm New Password",
        validators=[DataRequired(), EqualTo("new_password")],
    )
    submit = SubmitField("Change Password")
