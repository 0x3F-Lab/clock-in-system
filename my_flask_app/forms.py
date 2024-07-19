from models import People
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, TextAreaField, IntegerField, EmailField
from wtforms.validators import InputRequired, Length, ValidationError, Email, NumberRange
import re

# Custom validator - apply validator to email or username depending on login type
def email_or_id(form, field):
    if '@' in field.data:
        Email()(form, field)
    else:
        try:
            employee_id = int(field.data)
        except (ValueError, TypeError):
            raise ValidationError("Invalid employee ID format.")

# Ensure no spaces in the field
def noSpaces(form, field):
    if ' ' in field.data:
        raise ValidationError("The username must not contain spaces.")

# Password validation
def pass_characters(form, field):
    if not re.match(r'^[a-zA-Z0-9!?+_\-]+$', field.data):
        raise ValidationError("Password can only include letters, numbers, and the following special characters: !, ?, +, -, _.")

def pass_digit(form, field):
    if not re.search(r'[0-9]', field.data):
        raise ValidationError("Password must include at least one number.")

def pass_uppercase(form, field):
    if not re.search(r'[A-Z]', field.data):
        raise ValidationError("Password must include at least one uppercase letter.")


class SignupForm(FlaskForm):
    employee_id = IntegerField(
        'Employee ID',
        validators=[InputRequired()],
        render_kw={"placeholder": "Employee ID", "class": "form-control form-control-lg"})

    email = EmailField(
        'Email',
        validators=[InputRequired(), Email(message='Invalid email address.')],
        render_kw={"placeholder": "Email", "class": "form-control form-control-lg"})

    password = PasswordField(
        'Password', 
        validators=[InputRequired(), Length(min=5, max=25), pass_characters, pass_digit, pass_uppercase],
        render_kw={"placeholder": "Password", "class": "form-control form-control-lg"})
    
    submit = SubmitField("Register",
                        id='signup-submit-button',
                        render_kw={"class": "btn btn-success rounded"})

    def validate_employee_id(self, employee_id):
        employee = People.query.filter_by(person_id=employee_id.data).first()
        if not employee:
            raise ValidationError("Employee ID does not exist.")
        if employee.email and employee.password:
            raise ValidationError("This Employee ID is already associated with a registered account.")

    def validate_email(self, email):
        existing_email = People.query.filter_by(email=email.data).first()
        if existing_email:
            raise ValidationError("An account with this email already exists. Please use a different email.")


class LoginForm(FlaskForm):
    login = StringField(
        'Email or Employee ID', 
        validators=[InputRequired(), email_or_id], 
        render_kw={"placeholder": "Email/ID", "class": "form-control form-control-lg"})

    password = PasswordField(
        'Password', 
        validators=[InputRequired(), Length(min=5, max=25)], 
        render_kw={"placeholder": "Password", "class": "form-control form-control-lg"})

    remember_me = BooleanField('Remember me')

    submit = SubmitField("Login",
                        id='login-submit-button',
                        render_kw={"class": "btn btn-success rounded"})