"""FR-035: outbound email uses the contact's recorded language, defaulting to Arabic."""

import pytest
from django.core import mail
from django.urls import reverse

from apps.messaging.services.outbound import language_for_contact


@pytest.mark.django_db
def test_language_follows_the_contacts_recorded_preference(contact):
    contact.preferred_language = "en"
    contact.save(update_fields=["preferred_language"])
    assert language_for_contact(contact) == "en"


@pytest.mark.django_db
def test_language_defaults_to_arabic_when_unknown(contact):
    contact.preferred_language = ""
    contact.save(update_fields=["preferred_language"])
    assert language_for_contact(contact) == "ar"


@pytest.mark.django_db
def test_reply_email_is_written_in_the_contacts_language(agent_client, ticket):
    ticket.contact.preferred_language = "ar"
    ticket.contact.save(update_fields=["preferred_language"])
    mail.outbox.clear()

    agent_client.post(reverse("tickets:reply", args=[ticket.reference]), {"body": "تم فتح تحقيق."})

    sent = mail.outbox[0]
    assert "رقم الطلب" in sent.body  # the Arabic reply template, not the English one


@pytest.mark.django_db
def test_english_contact_gets_the_english_template(agent_client, ticket):
    ticket.contact.preferred_language = "en"
    ticket.contact.save(update_fields=["preferred_language"])
    mail.outbox.clear()

    agent_client.post(
        reverse("tickets:reply", args=[ticket.reference]), {"body": "Investigation opened."}
    )

    sent = mail.outbox[0]
    assert "Reference:" in sent.body
