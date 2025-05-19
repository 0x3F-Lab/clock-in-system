import re

from django import forms
from django.utils.timezone import now
from django.core.exceptions import ValidationError
from auth_app.models import User, Notification, Store
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
    retype_password = forms.CharField(
        label="Retype Password",
        required=True,
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "Retype your Password",
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

    def clean_retype_password(self):
        password = self.cleaned_data.get("password", "")
        retype_password = self.cleaned_data.get("retype_password", "")
        if password != retype_password:
            raise ValidationError("Both password fields must match.")


class ManualClockingForm(forms.Form):
    store_pin = forms.CharField(
        label="Store PIN",
        required=True,
        max_length=255,
        widget=forms.PasswordInput(
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
        widget=forms.PasswordInput(
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


class NotificationForm(forms.Form):
    RECIPIENT_CHOICES = [
        ("store_managers", "Store Managers Only"),
        (
            "store_employees",
            "Store Employees (Every active user in your selected store)",
        ),
        ("all_users", "All Users (Site-wide)"),
        ("all_managers", "All Managers (Site-wide)"),
        ("site_admins", "Site Administrators"),
    ]

    title = forms.CharField(
        max_length=200,
        required=True,
        label="Title",
        widget=forms.TextInput(
            attrs={"placeholder": "Enter notification title", "class": "w-100"}
        ),
    )
    message = forms.CharField(
        required=True,
        label="Message",
        max_length=750,
        help_text="Max 750 characters. Newlines and Unicode allowed.",
        widget=forms.Textarea(
            attrs={"rows": 4, "class": "w-100 p-2", "placeholder": "Enter message"}
        ),
    )
    recipient_group = forms.ChoiceField(
        choices=[],
        required=True,
        label="Send To",
        widget=forms.Select(attrs={"class": "form-select w-100 p-2"}),
    )
    # THIS TURNS FROM AN ID INPUTTED ON CLIENT SIDE TO A STORE OBJECT ONCE VALIDATED
    store = forms.ModelChoiceField(
        queryset=Store.objects.filter(is_active=True),
        required=False,
        widget=forms.HiddenInput(),
        label="",
    )
    notification_type = forms.ChoiceField(
        choices=[],
        required=True,
        label="Notification Type",
        widget=forms.Select(attrs={"class": "form-select w-100 p-2"}),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.user = user

        # Limit notification types based on user role
        type_choices = Notification.Type.choices

        type_choices = [
            (Notification.Type.GENERAL, Notification.Type.GENERAL.label),
            (Notification.Type.EMERGENCY, Notification.Type.EMERGENCY.label),
        ]

        if user.is_manager:
            type_choices.extend(
                [
                    (
                        Notification.Type.MANAGER_NOTE,
                        Notification.Type.MANAGER_NOTE.label,
                    ),
                    (
                        Notification.Type.SCHEDULE_CHANGE,
                        Notification.Type.SCHEDULE_CHANGE.label,
                    ),
                ]
            )

        if user.is_hidden:
            type_choices.extend(
                [
                    (
                        Notification.Type.SYSTEM_ALERT,
                        Notification.Type.SYSTEM_ALERT.label,
                    ),
                    (
                        Notification.Type.ADMIN_NOTE,
                        Notification.Type.ADMIN_NOTE.label,
                    ),
                ]
            )

        self.fields["notification_type"].choices = type_choices

        # Default: only allow sending to managers
        recipient_choices = [
            ("store_managers", "Store Managers Only"),
            ("site_admins", "Site Administrators"),
        ]

        if user.is_manager:
            # Managers can send to other store employees
            recipient_choices.append(
                (
                    "store_employees",
                    "Store Employees (Every active user in your selected store)",
                )
            )

        if user.is_hidden:
            # Hidden (super admins) can send to all users site-wide
            recipient_choices.append(("all_users", "All Users (Site-wide)"))
            recipient_choices.append(("all_managers", "All Managers (Site-wide)"))

        self.fields["recipient_group"].choices = recipient_choices

    def clean_notification_type(self):
        notification_type = self.cleaned_data.get("notification_type")
        recipient_group = self.cleaned_data.get("recipient_group")
        print(recipient_group)

        # Validate combinations
        if (
            notification_type == Notification.Type.MANAGER_NOTE
            and recipient_group != "store_employees"
        ):
            raise ValidationError("Manager Notes can only be sent to Store Employees.")

        elif (
            notification_type == Notification.Type.SYSTEM_ALERT
            and recipient_group not in ["all_users", "all_managers"]
        ):
            raise ValidationError(
                "System Alerts can only be sent to all users or all managers."
            )

        elif (
            notification_type == Notification.Type.SCHEDULE_CHANGE
            and recipient_group != "store_employees"
        ):
            raise ValidationError(
                "Schedule Change notifications must target store employees."
            )

        elif notification_type == Notification.Type.AUTOMATIC_ALERT:
            raise ValidationError("Cannot use message type Automatic Alert.")

        elif notification_type not in Notification.Type:
            raise ValidationError("Invalid notification type.")

        return notification_type

    def clean_recipient_group(self):
        recipient_group = self.cleaned_data.get("recipient_group")

        # Validate options
        if not any(key == recipient_group for key, _ in self.RECIPIENT_CHOICES):
            raise ValidationError("Invalid recipient group choice.")

        return recipient_group

    def clean_message(self):
        msg = self.cleaned_data["message"]
        if len(msg.strip()) == 0:
            raise ValidationError("Message cannot be empty or just whitespace.")
        return msg

    def clean(self):
        cleaned_data = super().clean()
        recipient_group = cleaned_data.get("recipient_group")
        store = cleaned_data.get("store")

        if not store and recipient_group not in ["all_users", "all_managers"]:
            raise ValidationError(
                "You must select a store for store-based notifications."
            )

        return cleaned_data
