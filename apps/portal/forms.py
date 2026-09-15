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
from apps.tickets.models import Category


def _within_the_limit(text):
    """The shared length check for anything a customer writes (FR-024).

    `Message.body` and `Ticket.description` are TextFields with no limit at all, so nothing
    downstream would refuse a ten-megabyte paste. The check has to be made deliberately, on
    the way in — and in ONE place, because the reply screen and the new-request screen
    disagreeing about how much a customer may write is how somebody learns the product is
    arbitrary.

    Says which problem it is, and by how much: "invalid" leaves somebody who has written four
    paragraphs guessing whether to shorten them or retype them.
    """
    text = (text or "").strip()
    limit = settings.PORTAL_MESSAGE_MAX_LENGTH

    if len(text) > limit:
        over = len(text) - limit
        # ngettext, not an "(s)" on the end. Arabic has six plural forms, so this is not a
        # problem English can solve on Arabic's behalf.
        raise ValidationError(
            ngettext(
                "This is too long by %(over)d character. The limit is %(limit)d.",
                "This is too long by %(over)d characters. The limit is %(limit)d.",
                over,
            )
            % {"over": over, "limit": limit}
        )

    return text


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
        # Shared with NewRequestForm. The reply screen and the new-request screen disagreeing
        # about how much a customer may write is how somebody learns the product is arbitrary.
        return _within_the_limit(self.cleaned_data.get("body"))


class NewRequestForm(forms.Form):
    """Raising a request as a signed-in customer.

    No name, no email address (FR-023). They proved an address to get here, and a form that
    asked again would be trusting whatever they typed over the thing that was actually
    checked — a worse guarantee as well as a worse experience.

    No honeypot and no minimum-completion-time field either. Those belong on the anonymous
    public form, where nothing else stands between a script and a ticket. Registration,
    confirmation and a rate limit already sit in front of this one, and making a signed-in
    customer wait three seconds before submitting would be guarding a door already locked.
    """

    category = forms.ModelChoiceField(
        label=_("What is this about?"),
        queryset=Category.objects.filter(is_active=True),
        error_messages={"required": _("Choose what this is about.")},
    )
    subject = forms.CharField(
        label=_("Subject"),
        max_length=255,
        strip=True,
        error_messages={"required": _("Give the request a short subject.")},
    )
    description = forms.CharField(
        label=_("What has happened?"),
        widget=forms.Textarea(attrs={"rows": 6}),
        strip=True,
        error_messages={"required": _("Describe what has happened.")},
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Categories are stored with an English name and an Arabic one. `__str__` returns the
        # English name — correct for the admin and the audit log, wrong on a screen a customer
        # reads, where it put "Billing" next to a label reading الموضوع.
        self.fields["category"].label_from_instance = lambda obj: obj.display_name

    def clean_description(self):
        return _within_the_limit(self.cleaned_data.get("description"))


class NewPasswordForm(forms.Form):
    """Choosing a replacement password from a reset link.

    The strength check is NOT here. It runs in `passwords.complete_reset`, after the link has
    been verified, so that the policy is applied in one place for registration and for reset
    alike — two forms each carrying their own copy is two policies that agree until one of
    them is edited.
    """

    password = forms.CharField(
        label=_("New password"),
        widget=forms.PasswordInput(render_value=False),
        strip=False,
        max_length=128,
        error_messages={"required": _("Choose a new password.")},
    )
