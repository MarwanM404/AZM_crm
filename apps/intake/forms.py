"""
Public intake form (FR-001, FR-005, FR-006).

Two abuse-protection signals beyond django-ratelimit (research.md #6): a honeypot field real
browsers never fill in, and a minimum time-since-render check that catches scripted submitters
faster than any human could type.
"""

import time

from django import forms
from django.utils.translation import gettext_lazy as _

from apps.tickets.models import Category

MIN_SECONDS_TO_COMPLETE = 3


class IntakeForm(forms.Form):
    full_name = forms.CharField(label=_("Your name"), max_length=200)
    email = forms.EmailField(label=_("Email address"))
    phone = forms.CharField(label=_("Phone number"), max_length=30, required=False)
    category = forms.ModelChoiceField(
        label=_("Category"), queryset=Category.objects.filter(is_active=True)
    )
    subject = forms.CharField(label=_("Subject"), max_length=255)
    description = forms.CharField(label=_("Description"), widget=forms.Textarea)

    # Honeypot: real visitors never see or fill this field (hidden by CSS, not `type=hidden`,
    # since some bots skip literal hidden inputs but not CSS-hidden ones).
    company_website = forms.CharField(required=False, widget=forms.TextInput())

    # Minimum completion time (research.md #6).
    rendered_at = forms.FloatField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The same fix as the portal's form, for the same reason: this is the screen anonymous
        # Arabic-speaking customers actually meet, and it has been offering them English
        # category names since the MVP. Nothing else about this form changes (FR-025).
        self.fields["category"].label_from_instance = lambda obj: obj.display_name

    def clean_company_website(self):
        value = self.cleaned_data.get("company_website")
        if value:
            raise forms.ValidationError(_("Submission rejected."))
        return value

    def clean_rendered_at(self):
        rendered_at = self.cleaned_data.get("rendered_at")
        if rendered_at is not None and (time.time() - rendered_at) < MIN_SECONDS_TO_COMPLETE:
            raise forms.ValidationError(_("Submission rejected."))
        return rendered_at
