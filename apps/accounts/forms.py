from django import forms
from django.contrib.auth import authenticate
from django.utils.translation import gettext_lazy as _


class SignInForm(forms.Form):
    email = forms.EmailField(label=_("Email"))
    password = forms.CharField(label=_("Password"), widget=forms.PasswordInput)

    def clean(self):
        cleaned = super().clean()
        email = cleaned.get("email")
        password = cleaned.get("password")
        if email and password:
            user = authenticate(email=email, password=password)
            if user is None:
                raise forms.ValidationError(_("Invalid email or password."))
            cleaned["user"] = user
        return cleaned
