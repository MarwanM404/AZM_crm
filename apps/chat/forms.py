"""
The pre-chat form (FR-002).

Deliberately short: every field is one more reason to close the panel instead of asking the
question. Name and email only, matched against contacts exactly as the request form does, so
chat does not become a second way to create customers.
"""

from django import forms
from django.utils.translation import gettext_lazy as _

from apps.tickets.models import Category


class PreChatForm(forms.Form):
    full_name = forms.CharField(label=_("Your name"), max_length=200)
    email = forms.EmailField(label=_("Email address"))
    subject = forms.CharField(label=_("What can we help with?"), max_length=255)
    category = forms.ModelChoiceField(
        label=_("Category"), queryset=Category.objects.filter(is_active=True)
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Categories carry an English name and an Arabic one. `Category.__str__` returns the
        # English one — right for the admin and the audit log, wrong on a form a customer
        # fills in, where it put "Logistics" among Arabic labels.
        #
        # The same fix the intake form and the portal's new-request form already carry. This
        # one was missed because no browser check covered the widget until the public screens
        # joined the Arabic sweep, which then failed on its first run.
        self.fields["category"].label_from_instance = lambda obj: obj.display_name
