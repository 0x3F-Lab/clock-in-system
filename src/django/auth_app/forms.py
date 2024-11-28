from django import forms
from django.contrib.auth.hashers import make_password
from .models import User


class NewUserForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput
    )  # Use PasswordInput to mask input

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "password"]

    def save(self):
        try:
            # Create a new User instance with cleaned data
            user = User(
                first_name=self.cleaned_data["first_name"],
                last_name=self.cleaned_data["last_name"],
                email=self.cleaned_data["email"],
                password=make_password(
                    self.cleaned_data["password"]
                ),  # Hash the password
            )
            user.save()  # Save the user instance to the database
            return user
        except Exception as e:
            raise e  # Re-raise the issue
