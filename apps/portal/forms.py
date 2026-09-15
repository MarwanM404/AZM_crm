"""
The portal's forms.

`RegistrationForm` validates the password and NOT whether the address is already taken. That
omission is the feature: a form that added "this address is already registered" would be a
correct, helpful, conventional Django form and would defeat FR-007 on the one screen it
matters most. Whether an address is known is decided in the service, which tells nobody.
"""

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

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


class ReplyForm(forms.Form):
    """A customer's reply.

    The maximum comes from settings at validation time rather than from a field argument
    evaluated at import, so it can be changed without a release (FR-024) and moved by the
    `settings` fixture in a test.

    `Message.body` is a TextField with no limit at all, so nothing downstream would refuse a
    ten-megabyte paste — which is why the check has to be made deliberately here, on the way
    in, rather than left to the database to enforce.
    """

    body = forms.CharField(
        label=_("Your reply"),
        widget=forms.Textarea(attrs={"rows": 5}),
        strip=True,
        # Not a check inside `clean_body`. Written that way first, and the branch was
        # unreachable: `required` runs before any `clean_<field>` method, so the custom
        # message never appeared and the customer read Django's "This field is required." —
        # accurate, bureaucratic, and not what a support desk should say to somebody who has
        # just come back to chase a delivery. Found by clicking the button on an empty box.
        error_messages={"required": _("Write something before sending.")},
    )

    def clean_body(self):
        body = (self.cleaned_data.get("body") or "").strip()

        limit = settings.PORTAL_MESSAGE_MAX_LENGTH
        if len(body) > limit:
            # Says WHICH problem it is, and by how much. "Invalid" leaves somebody who has
            # written four paragraphs guessing whether to shorten them or retype them.
            over = len(body) - limit
            # ngettext, not a format string with an "s" on the end. Arabic has six plural
            # forms, so "character(s)" is not a problem English can solve on its behalf.
            raise ValidationError(
                ngettext(
                    "This is too long by %(over)d character. The limit is %(limit)d.",
                    "This is too long by %(over)d characters. The limit is %(limit)d.",
                    over,
                )
                % {"over": over, "limit": limit}
            )

        return body
