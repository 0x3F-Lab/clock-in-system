from django import forms


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
        required=False, min_value=0, widget=forms.HiddenInput()
    )

    latitude = forms.DecimalField(
        required=True, max_digits=10, decimal_places=7, widget=forms.HiddenInput()
    )

    longitude = forms.DecimalField(
        required=True, max_digits=10, decimal_places=7, widget=forms.HiddenInput()
    )
