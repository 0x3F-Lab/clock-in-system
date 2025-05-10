import re

from django import forms
from django.utils.timezone import now
from django.core.exceptions import ValidationError
from auth_app.models import User
from clock_in_system.settings import (
    VALID_NAME_PATTERN,
    VALID_PHONE_NUMBER_PATTERN,
    VALID_PASSWORD_PATTERN,
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
)


class LoginForm(forms.Form):
    email = forms.EmailField(
        label="Email",
        required=True,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Email",
                "class": "w-100 form-control form-control-lg",
            }
        ),
    )
    password = forms.CharField(
        label="Password",
        required=True,
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "Password",
                "class": "w-100 form-control form-control-lg",
            }
        ),
    )

    def clean_email(self):
        return self.cleaned_data.get("email", "").strip().lower()


class AccountSetupForm(forms.Form):
    email = forms.EmailField(
        label="Email",
        required=True,
        widget=forms.EmailInput(
            attrs={
                "placeholder": "Email",
                "class": "w-100 form-control form-control-lg",
            }
        ),
    )
    first_name = forms.CharField(
        label="First Name",
        required=True,
        widget=forms.TextInput(
            attrs={
                "placeholder": "First Name",
                "class": "w-100 form-control form-control-lg",
            }
        ),
    )
    last_name = forms.CharField(
        label="Last Name",
        required=True,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Last Name",
                "class": "w-100 form-control form-control-lg",
            }
        ),
    )
    phone_number = forms.CharField(
        label="Phone Number",
        required=False,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Phone Number",
                "class": "w-100 form-control form-control-lg",
            }
        ),
    )
    birth_date = forms.DateField(
        label="Date of Birth",
        required=False,
        widget=forms.DateInput(
            attrs={
                "placeholder": "YYYY-MM-DD",
                "class": "w-100 form-control form-control-lg",
                "type": "date",
            }
        ),
    )
    password = forms.CharField(
        label="Password",
        required=True,
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "Create a Password",
                "class": "w-100 form-control form-control-lg",
            }
        ),
    )

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip().lower()
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise ValidationError("No account found with this email address.")
        if user.is_setup:
            raise ValidationError("This account has already been set up.")
        return email

    def clean_first_name(self):
        first_name = self.cleaned_data.get("first_name", "").strip()
        if len(first_name) > 100:
            raise ValidationError(
                "First name cannot be longer than 100 characters long."
            )
        if not re.match(VALID_NAME_PATTERN, first_name):
            raise ValidationError("First name contains invalid characters.")
        return first_name.title()

    def clean_last_name(self):
        last_name = self.cleaned_data.get("last_name", "").strip()
        if len(last_name) > 100:
            raise ValidationError(
                "Last name cannot be longer than 100 characters long."
            )
        if not re.match(VALID_NAME_PATTERN, last_name):
            raise ValidationError("Last name contains invalid characters.")
        return last_name.title()

    def clean_phone_number(self):
        phone = self.cleaned_data.get("phone_number", "") or None
        if phone:
            if len(phone) > 15:
                raise ValidationError(
                    "Phone number cannot be longer than 15 characters long."
                )
            if not re.match(VALID_PHONE_NUMBER_PATTERN, phone):
                raise ValidationError("Phone number contains invalid characters.")
        return phone.strip() if phone else phone

    def clean_birth_date(self):
        dob = self.cleaned_data.get("birth_date") or None
        if dob:
            today = now().date()
            if dob >= today:
                raise ValidationError("Date of birth must be before today.")
        return dob

    def clean_password(self):
        password = self.cleaned_data.get("password", "")
        if len(password) < PASSWORD_MIN_LENGTH:
            raise ValidationError(
                f"Password must be at least {PASSWORD_MIN_LENGTH} characters long."
            )
        if len(password) > PASSWORD_MAX_LENGTH:
            raise ValidationError(
                f"Password cannot be longer than {PASSWORD_MAX_LENGTH} characters long."
            )
        if not re.search(VALID_PASSWORD_PATTERN, password):
            raise ValidationError(
                "Password must contain at least one uppercase letter, one lowercase letter, and one number."
            )
        return password


class ManualClockingForm(forms.Form):
    store_pin = forms.CharField(
        label="Store PIN",
        required=True,
        max_length=255,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Store PIN",
                "maxlength": "255",
                "class": "w-100 form-control form-control-lg",
            }
        ),
    )

    employee_pin = forms.CharField(
        label="Employee PIN",
        required=True,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Employee PIN",
                "class": "w-100 form-control form-control-lg",
            }
        ),
    )

    # Hidden input as the page uses an input outside the form which is then handled by js
    deliveries = forms.IntegerField(
        required=False, min_value=0, initial=0, widget=forms.HiddenInput()
    )

    latitude = forms.DecimalField(
        required=True, max_digits=10, decimal_places=7, widget=forms.HiddenInput()
    )

    longitude = forms.DecimalField(
        required=True, max_digits=10, decimal_places=7, widget=forms.HiddenInput()
    )
