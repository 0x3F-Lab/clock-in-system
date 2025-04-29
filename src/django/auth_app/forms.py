from django import forms


class LoginForm(forms.Form):
    email = forms.EmailField(
        required=True,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Email",
                "class": "w-100 form-control form-control-lg",
            }
        ),
    )
    password = forms.CharField(
        required=True,
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "Password",
                "class": "w-100 form-control form-control-lg",
            }
        ),
    )


class ManualClockingForm(forms.Form):
    store_pin = forms.CharField(
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
        required=True,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Employee PIN",
                "class": "w-100 form-control form-control-lg",
            }
        ),
    )

    deliveries = forms.IntegerField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(
            attrs={
                "placeholder": "Deliveries (if any)",
                "class": "form-control",
            }
        ),
    )
