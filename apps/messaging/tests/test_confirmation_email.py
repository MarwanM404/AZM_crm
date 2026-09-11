"""FR-004: confirmation contains the reference and a reply-to token, in the visitor's language."""

import time

import pytest
from django.core import mail
from django.urls import reverse

from apps.tickets.models import Ticket


@pytest.mark.django_db
def test_confirmation_email_is_sent_with_reference_and_reply_to(client, branch, category, settings):
    payload = {
        "full_name": "Jane Doe",
        "email": "jane@example.com",
        "category": category.pk,
        "subject": "Help",
        "description": "Something broke",
        "company_website": "",
        "rendered_at": time.time() - 5,
    }
    client.post(reverse("intake:form"), payload)
    ticket = Ticket.objects.get()

    assert len(mail.outbox) == 1
    sent = mail.outbox[0]
    assert ticket.reference in sent.body
    assert sent.to == ["jane@example.com"]
    assert sent.reply_to == [f"support+{ticket.reference}@{settings.SUPPORT_EMAIL_DOMAIN}"]
