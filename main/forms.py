from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (
    StringField,
    PasswordField,
    SubmitField,
    SelectField,
    DecimalField,
    DateField,
    TextAreaField,
    FloatField,
    BooleanField,
    HiddenField,
)
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    ValidationError,
    Length,
    Optional,
    NumberRange,
)
from .models import User, Client, Company, InsuranceProduct


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")


class RegistrationForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired(), Length(min=2, max=120)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    phone = StringField("Phone", validators=[Optional(), Length(max=30)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match")],
    )
    submit = SubmitField("Register")


class ProfileForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired(), Length(min=2, max=120)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    phone = StringField("Phone", validators=[Optional(), Length(max=30)])
    profile_picture = FileField(
        "Profile Picture",
        validators=[FileAllowed(["jpg", "jpeg", "png", "gif"], "Images only!"), Optional()]
    )
    submit = SubmitField("Update Profile")


class PasswordChangeForm(FlaskForm):
    current_password = PasswordField("Current Password", validators=[DataRequired()])
    new_password = PasswordField("New Password", validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[DataRequired(), EqualTo("new_password", message="Passwords must match")],
    )
    submit = SubmitField("Change Password")


class ClientForm(FlaskForm):
    first_name = StringField("First Name", validators=[DataRequired(), Length(min=2, max=100)])
    last_name = StringField("Last Name", validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField("Email", validators=[Optional(), Email()])
    phone = StringField("Phone", validators=[Optional(), Length(max=30)])
    address = TextAreaField("Address", validators=[Optional()])
    city = StringField("City", validators=[Optional(), Length(max=100)])
    state = StringField("State", validators=[Optional(), Length(max=100)])
    postal_code = StringField("Postal Code", validators=[Optional(), Length(max=20)])
    id_number = StringField("ID Number", validators=[Optional(), Length(max=50)])
    date_of_birth = DateField("Date of Birth", validators=[Optional()])
    submit = SubmitField("Save Client")


class CompanyForm(FlaskForm):
    name = StringField("Company Name", validators=[DataRequired(), Length(min=2, max=150)])
    contact_email = StringField("Email", validators=[Optional(), Email()])
    phone = StringField("Phone", validators=[Optional(), Length(max=50)])
    address = TextAreaField("Address", validators=[Optional()])
    website = StringField("Website", validators=[Optional(), Length(max=255)])
    description = TextAreaField("Description", validators=[Optional()])
    submit = SubmitField("Save Company")


class InsuranceProductForm(FlaskForm):
    company_id = SelectField("Company", coerce=int, validators=[DataRequired()])
    name = StringField("Product Name", validators=[DataRequired(), Length(min=2, max=150)])
    description = TextAreaField("Description", validators=[Optional()])
    coverage_type = StringField("Coverage Type", validators=[Optional(), Length(max=100)])
    submit = SubmitField("Save Product")


class CommissionRuleForm(FlaskForm):
    company_id = SelectField("Company", coerce=int, validators=[DataRequired()])
    product_id = SelectField("Product", coerce=int, validators=[DataRequired()])
    commission_percent = FloatField(
        "Commission %",
        validators=[DataRequired(), NumberRange(min=0, max=100)],
    )
    description = StringField("Description", validators=[Optional(), Length(max=255)])
    is_active = BooleanField("Active", default=True)
    submit = SubmitField("Save Commission Rule")


class PolicyForm(FlaskForm):
    client_id = SelectField("Client", coerce=int, validators=[DataRequired()])
    company_id = SelectField("Company", coerce=int, validators=[DataRequired()])
    product_id = SelectField("Product", coerce=int, validators=[DataRequired()])
    
    policy_number = StringField("Policy Number", validators=[DataRequired(), Length(min=2, max=100)])
    coverage_amount = DecimalField("Coverage Amount", validators=[DataRequired(), NumberRange(min=0)])
    premium_amount = DecimalField("Premium Amount", validators=[DataRequired(), NumberRange(min=0)])
    
    premium_frequency = SelectField(
        "Premium Frequency",
        choices=[("monthly", "Monthly"), ("quarterly", "Quarterly"), ("annual", "Annual")],
        validators=[DataRequired()],
    )
    
    start_date = DateField("Start Date", validators=[DataRequired()])
    end_date = DateField("End Date", validators=[DataRequired()])
    
    submit = SubmitField("Save Policy")


class PremiumRemittanceForm(FlaskForm):
    amount = DecimalField("Amount", validators=[DataRequired(), NumberRange(min=0)])
    payment_method = SelectField(
        "Payment Method",
        choices=[
            ("bank_transfer", "Bank Transfer"),
            ("cash", "Cash"),
            ("mobile_money", "Mobile Money"),
        ],
        validators=[DataRequired()],
    )
    reference = StringField("Reference/Transaction ID", validators=[Optional(), Length(max=200)])
    notes = TextAreaField("Notes", validators=[Optional()])
    submit = SubmitField("Record Remittance")


class BulkUploadForm(FlaskForm):
    upload_type = SelectField(
        "Upload Type",
        choices=[
            ("clients", "Clients"),
            ("policies", "Policies"),
        ],
        validators=[DataRequired()],
    )
    file = FileField(
        "Excel File",
        validators=[
            DataRequired(),
            FileAllowed(["xlsx", "xls", "csv"], "Excel/CSV files only!"),
        ],
    )
    submit = SubmitField("Upload")


class ManualJournalForm(FlaskForm):
    description = StringField("Description", validators=[DataRequired(), Length(min=5, max=255)])
    debit_account = StringField("Debit Account", validators=[DataRequired(), Length(max=100)])
    credit_account = StringField("Credit Account", validators=[DataRequired(), Length(max=100)])
    amount = DecimalField("Amount", validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField("Record Entry")

