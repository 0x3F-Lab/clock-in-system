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
