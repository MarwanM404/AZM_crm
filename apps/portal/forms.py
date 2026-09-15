"""
The portal's forms.

`RegistrationForm` validates the password and NOT whether the address is already taken. That
omission is the feature: a form that added "this address is already registered" would be a
correct, helpful, conventional Django form and would defeat FR-007 on the one screen it
matters most. Whether an address is known is decided in the service, which tells nobody.
"""

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from apps.portal.services import passwords


class EmailForm(forms.Form):
    """Asking for an address and nothing else: resending a confirmation, starting a reset."""

    email = forms.EmailField(label=_("Email address"), max_length=254)


class RegistrationForm(forms.Form):
    email = forms.EmailField(label=_("Email address"), max_length=254)
    password = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(render_value=False),
        strip=False,
        max_length=128,
    )

    def clean_password(self):
        password = self.cleaned_data.get("password", "")
        try:
            passwords.validate(password, email=self.data.get("email"))
        except ValidationError as error:
            # Re-raised against this field so the reasons appear next to the box they are
            # about. Django's validators return a list of messages, each naming one rule —
            # "too short", "too common" — and a customer who is told only "invalid" tries
            # another password of the same shape.
            raise ValidationError(error.messages) from error
        return password


class SignInForm(forms.Form):
    email = forms.EmailField(label=_("Email address"), max_length=254)
    password = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(render_value=False),
        strip=False,
        max_length=128,
    )
