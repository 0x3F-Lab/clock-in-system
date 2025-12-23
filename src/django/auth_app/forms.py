import re
import auth_app.utils as util

from bleach import clean
from django import forms
from django.conf import settings
from django.utils.timezone import now
from django.core.exceptions import ValidationError
from auth_app.models import User, Notification, Store


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
        email = self.cleaned_data.get("email", "")
        return util.sanitise_plain_text(email).lower()


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
        email = self.cleaned_data.get("email", "")
        email = util.sanitise_plain_text(email).lower()
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise ValidationError("No account found with this email address.")
        if user.is_setup:
            raise ValidationError("This account has already been set up.")
        return email

    def clean_first_name(self):
        first_name = util.sanitise_plain_text(self.cleaned_data.get("first_name", ""))
        if len(first_name) > 100:
            raise ValidationError(
                "First name cannot be longer than 100 characters long."
            )
        if not re.match(settings.VALID_NAME_PATTERN, first_name):
            raise ValidationError("First name contains invalid characters.")
        return first_name.title()

    def clean_last_name(self):
        last_name = util.sanitise_plain_text(self.cleaned_data.get("last_name", ""))
        if len(last_name) > 100:
            raise ValidationError(
                "Last name cannot be longer than 100 characters long."
            )
        if not re.match(settings.VALID_NAME_PATTERN, last_name):
            raise ValidationError("Last name contains invalid characters.")
        return last_name.title()

    def clean_phone_number(self):
        phone = self.cleaned_data.get("phone_number", "") or None
        if phone:
            phone = util.sanitise_plain_text(phone)
            if len(phone) > 15:
                raise ValidationError(
                    "Phone number cannot be longer than 15 characters long."
                )
            if not re.match(settings.VALID_PHONE_NUMBER_PATTERN, phone):
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
        password = util.sanitise_plain_text(self.cleaned_data.get("password", ""))
        if len(password) < settings.PASSWORD_MIN_LENGTH:
            raise ValidationError(
                f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters long."
            )
        if len(password) > settings.PASSWORD_MAX_LENGTH:
            raise ValidationError(
                f"Password cannot be longer than {settings.PASSWORD_MAX_LENGTH} characters long."
            )
        if not re.search(settings.VALID_PASSWORD_PATTERN, password):
            raise ValidationError(
                "Password must contain at least one uppercase letter, one lowercase letter, and one number."
            )
        return password

    def clean_retype_password(self):
        password = util.sanitise_plain_text(self.cleaned_data.get("password", ""))
        retype_password = util.sanitise_plain_text(
            self.cleaned_data.get("retype_password", "")
        )
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
        required=True, max_digits=25, decimal_places=22, widget=forms.HiddenInput()
    )

    longitude = forms.DecimalField(
        required=True, max_digits=25, decimal_places=22, widget=forms.HiddenInput()
    )

    def clean_store_pin(self):
        store_pin = util.sanitise_plain_text(self.cleaned_data.get("store_pin", ""))
        return store_pin

    def clean_employee_pin(self):
        employee_pin = util.sanitise_plain_text(
            self.cleaned_data.get("employee_pin", "")
        )
        return employee_pin


class NotificationForm(forms.Form):
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
        max_length=settings.NOTIFICATION_MESSAGE_MAX_LENGTH,
        help_text=f"Max {settings.NOTIFICATION_MESSAGE_MAX_LENGTH} characters. Newlines and Unicode allowed.",
        widget=forms.Textarea(
            attrs={"rows": 4, "class": "w-100 p-2", "placeholder": "Enter message"}
        ),
    )
    recipient_group = forms.ChoiceField(
        choices=[],  # Dynamnically adjusted in __init__
        required=True,
        label="Send To",
        widget=forms.Select(attrs={"class": "form-select w-100 p-2"}),
    )
    store = forms.ChoiceField(
        choices=[],  # Dynamnically adjusted in __init__
        required=False,
        widget=forms.Select(attrs={"class": "form-select w-100 p-2"}),
        label="Store",
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

        # ---------------- STORE CHOICES ----------------
        if user is not None:
            active_stores = user.get_associated_stores()
            self.fields["store"].choices = [
                (store.id, store.code) for store in active_stores
            ]
        else:
            self.fields["store"].choices = [("", "--- No available stores ---")]

        # ------------- NOTIFICATION TYPE CHOICES ---------------
        type_choices = [
            (Notification.Type.GENERAL.value, Notification.Type.GENERAL.label),
            (Notification.Type.EMERGENCY.value, Notification.Type.EMERGENCY.label),
        ]

        if user and user.is_manager():
            type_choices.extend(
                [
                    (
                        Notification.Type.MANAGER_NOTE.value,
                        Notification.Type.MANAGER_NOTE.label,
                    ),
                    (
                        Notification.Type.SCHEDULE_CHANGE.value,
                        Notification.Type.SCHEDULE_CHANGE.label,
                    ),
                ]
            )

        if user and user.is_hidden:
            type_choices.extend(
                [
                    (
                        Notification.Type.SYSTEM_ALERT.value,
                        Notification.Type.SYSTEM_ALERT.label,
                    ),
                    (
                        Notification.Type.ADMIN_NOTE.value,
                        Notification.Type.ADMIN_NOTE.label,
                    ),
                ]
            )

        self.fields["notification_type"].choices = type_choices

        # ------------- RECIPIENT GROUP CHOICES ---------------
        recipient_choices = [
            (
                Notification.RecipientType.STORE_MANAGERS.value,
                Notification.RecipientType.STORE_MANAGERS.label,
            ),
            (
                Notification.RecipientType.SITE_ADMINS.value,
                Notification.RecipientType.SITE_ADMINS.label,
            ),
        ]

        if user and user.is_manager():
            recipient_choices.append(
                (
                    Notification.RecipientType.STORE_EMPLOYEES.value,
                    Notification.RecipientType.STORE_EMPLOYEES.label,
                )
            )

        if user and user.is_hidden:
            recipient_choices.extend(
                [
                    (
                        Notification.RecipientType.ALL_USERS.value,
                        Notification.RecipientType.ALL_USERS.label,
                    ),
                    (
                        Notification.RecipientType.ALL_MANAGERS.value,
                        Notification.RecipientType.ALL_MANAGERS.label,
                    ),
                ]
            )

        self.fields["recipient_group"].choices = recipient_choices

    def clean_store(self):
        store_id = self.cleaned_data.get("store")

        if not store_id:
            # If no store provided for store-based message
            if self.cleaned_data.get("recipient_group") in [
                "store_managers",
                "store_employees",
            ]:
                raise ValidationError("Store not provided for store-based message.")
            return None

        # Validate that the store is in the allowed list for this user
        if not self.user:
            raise ValidationError("User is not authenticated or provided.")

        # Get user's allowed stores
        allowed_store_ids = {
            str(store.id) for store in self.user.get_associated_stores()
        }

        if str(store_id) not in allowed_store_ids:
            raise ValidationError("You do not have permission to select this store.")

        # Confirm store exists and is active
        try:
            return Store.objects.get(id=store_id, is_active=True)
        except Store.DoesNotExist:
            raise ValidationError("Selected store is invalid or inactive.")

    def clean_notification_type(self):
        notification_type = self.cleaned_data.get("notification_type")
        recipient_group = self.cleaned_data.get("recipient_group")
        store_id = self.cleaned_data.get("store", None)

        # Validate that the type is in the allowed list for this user
        if not self.user:
            raise ValidationError("User is not authenticated or provided.")

        elif (
            notification_type
            in [Notification.Type.MANAGER_NOTE, Notification.Type.SCHEDULE_CHANGE]
        ) and (not self.user.is_manager(store_id)):
            raise ValidationError("Not authorised to use that notification type.")

        elif (
            notification_type
            in [Notification.Type.SYSTEM_ALERT, Notification.Type.ADMIN_NOTE]
        ) and (not self.user.is_hidden):
            raise ValidationError("Not authorised to use that notification type.")

        elif notification_type == Notification.Type.AUTOMATIC_ALERT:
            raise ValidationError("Not authorised to use that notification type.")

        elif notification_type not in Notification.Type:
            raise ValidationError("Invalid notification type.")

        # Validate combinations
        if (
            notification_type == Notification.Type.MANAGER_NOTE
            and recipient_group
            not in [
                Notification.RecipientType.STORE_EMPLOYEES,
                Notification.RecipientType.SITE_ADMINS,
            ]
        ):
            raise ValidationError(
                "Manager Notes can only be sent to Store Employees or Site Admins."
            )

        elif (
            notification_type == Notification.Type.SYSTEM_ALERT
            and recipient_group
            not in [
                Notification.RecipientType.ALL_USERS,
                Notification.RecipientType.ALL_MANAGERS,
            ]
        ):
            raise ValidationError(
                "System Alerts can only be sent to all users or all managers."
            )

        elif (
            notification_type == Notification.Type.SCHEDULE_CHANGE
            and recipient_group != Notification.RecipientType.STORE_EMPLOYEES
        ):
            raise ValidationError(
                "Schedule Change can only be sent to store employees."
            )

        return notification_type

    def clean_recipient_group(self):
        recipient_group = self.cleaned_data.get("recipient_group")
        store_id = self.cleaned_data.get("store", None)
        allowed_choices = {
            Notification.RecipientType.STORE_MANAGERS.value,
            Notification.RecipientType.STORE_EMPLOYEES.value,
            Notification.RecipientType.SITE_ADMINS.value,
            Notification.RecipientType.ALL_USERS.value,
            Notification.RecipientType.ALL_MANAGERS.value,
        }

        # Validate that the type is in the allowed list for this user
        if not self.user:
            raise ValidationError("User is not authenticated or provided.")

        elif recipient_group not in allowed_choices:
            raise ValidationError("Invalid recipient group choice.")

        elif (
            recipient_group == Notification.RecipientType.STORE_EMPLOYEES
            and not self.user.is_manager(store_id)
        ):
            raise ValidationError(
                "Not authorised to use that recipient group for the selected Store."
            )

        elif (
            recipient_group
            in [
                Notification.RecipientType.ALL_USERS,
                Notification.RecipientType.ALL_MANAGERS,
            ]
            and not self.user.is_hidden
        ):
            raise ValidationError("Not authorised to use that recipient group.")

        return recipient_group

    def clean_message(self):
        msg = self.cleaned_data["message"]

        # Sanitise rendered HTML and apply markdowns
        safe_html = util.sanitise_markdown_message_text(msg)

        # Remove all tags to validate if there's text content
        bleached_html = clean(safe_html, tags=[], strip=True).strip()

        if len(bleached_html) == 0:
            raise ValidationError("Message cannot be empty or just whitespace.")
        if len(bleached_html) > settings.NOTIFICATION_MESSAGE_MAX_LENGTH:
            raise ValidationError(
                f"Message cannot exceed {settings.NOTIFICATION_MESSAGE_MAX_LENGTH} characters."
            )

        return safe_html

    def clean_title(self):
        title = self.cleaned_data["title"]

        # Sanitise rendered HTML and apply markdowns
        safe_html = util.sanitise_markdown_title_text(title)

        bleached_html = clean(safe_html, tags=[], strip=True).strip()

        if len(bleached_html) == 0:
            raise ValidationError("Title cannot be empty or just whitespace.")
        if len(bleached_html) > 200:
            raise ValidationError("Title cannot exceed 200 characters.")

        return safe_html

    def clean(self):
        cleaned_data = super().clean()
        recipient_group = cleaned_data.get("recipient_group")
        store = cleaned_data.get("store")

        if not store and recipient_group in [
            Notification.RecipientType.STORE_EMPLOYEES,
            Notification.RecipientType.STORE_MANAGERS,
        ]:
            raise ValidationError(
                "You must select a store for store-based notifications."
            )

        return cleaned_data


class AdminActionRepeatingShiftWriterForm(forms.Form):
    week_start_date = forms.DateField(
        required=True, widget=forms.DateInput(attrs={"type": "date"})
    )

    store = forms.ModelChoiceField(
        queryset=Store.objects.filter(
            is_active=True, is_scheduling_enabled=True, is_repeating_shifts_enabled=True
        ),
        required=True,
        label="Store",
    )
