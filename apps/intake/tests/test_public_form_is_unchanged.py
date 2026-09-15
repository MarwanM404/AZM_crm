"""
T071, FR-025: the anonymous request form works exactly as it does today.

Spec 004 adds a second path into ticket creation. This file exists because the risk of that is
not in the new path — it is that the old one is quietly altered while making room, and the
people who would notice are anonymous strangers with no account and no way to report it beyond
giving up.

These assertions are about the public form's OWN behaviour and deliberately do not mention the
portal. A test phrased as "the portal did not change this" stops making sense the moment
somebody changes the portal; a test phrased as "this is what the public form does" keeps
working, and is what FR-025 actually asks for.

The abuse protections are the part most likely to be lost in an extraction: they live on the
form rather than in the creation path, they have no visible effect when they work, and nothing
downstream would notice their absence.
"""

import time

import pytest
from django.conf import settings
from django.urls import reverse

from apps.customers.models import ContactDetail
from apps.tickets.models import Ticket

pytestmark = pytest.mark.django_db


def submit(client, category, follow=False, **overrides):
    """`follow` is a keyword of its own, not an override.

    Left in **overrides it went into the POST body instead, the response was an unfollowed
    302 with an empty page, and the assertion below failed against "" — a test failing for a
    reason that has nothing to do with what it is testing.
    """
    payload = {
        "full_name": "Sara Ahmed",
        "email": "sara@najd-trading.example",
        "phone": "",
        "category": category.pk,
        "subject": "Shipment marked delivered but not received",
        "description": "Nothing arrived at our office.",
        "company_website": "",
        "rendered_at": time.time() - 10,
    }
    payload.update(overrides)
    return client.post(reverse("intake:form"), payload, follow=follow)


def test_an_anonymous_visitor_can_still_raise_a_request(client, category, branch):
    response = submit(client, category)

    ticket = Ticket.objects.get()
    assert response.status_code == 302
    assert ticket.subject == "Shipment marked delivered but not received"
    assert (
        ticket.origin_channel == Ticket.Channel.WEB_FORM
    ), "The public form's channel changed. It is not the portal and must not claim to be."


def test_it_still_creates_the_contact_from_what_was_typed(client, category, branch):
    """The public form has no proven identity, so the name and address it is given are all
    there is. That is exactly why the portal does not work this way — and why this path must
    keep working this way."""
    submit(client, category, full_name="Faisal Someone", email="faisal@example.com")

    detail = ContactDetail.objects.get(value="faisal@example.com")
    assert detail.contact.full_name == "Faisal Someone"


def test_it_still_asks_for_a_name_and_an_address(client, category, branch):
    fields = set(client.get(reverse("intake:form")).context["form"].fields)

    assert {"full_name", "email"} <= fields


def test_the_honeypot_still_rejects(client, category, branch):
    """Invisible to a person, filled in by a bot. It has no effect when it works, so nothing
    downstream would report its absence."""
    submit(client, category, company_website="https://spam.example")

    assert not Ticket.objects.exists()


def test_the_minimum_completion_time_still_rejects(client, category, branch):
    submit(client, category, rendered_at=time.time())

    assert not Ticket.objects.exists()


def test_it_still_sends_a_confirmation(client, category, branch):
    from django.core import mail

    mail.outbox.clear()
    submit(client, category)

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["sara@najd-trading.example"]


def test_it_still_redirects_to_a_page_naming_only_the_reference(client, category, branch):
    response = submit(client, category, follow=True)
    body = response.content.decode()

    ticket = Ticket.objects.get()
    assert ticket.reference in body
    assert "sara@najd-trading.example" not in body, (
        "The confirmation page shows the submitted address, which the MVP deliberately kept "
        "off it."
    )


def test_it_is_still_reachable_without_signing_in(client):
    assert client.get(reverse("intake:form")).status_code == 200


def test_it_still_records_the_language_the_request_was_made_in(client, category, branch):
    """A new contact's `preferred_language` decides what language the desk's replies reach
    them in, forever after.

    This was untested until spec 004 extracted the creation path, and dropping the assignment
    passed the entire suite. Nothing fails when it is missing: the contact is created, the
    ticket is created, the confirmation goes out in the request's language — and every
    message after that arrives in the default, to somebody who wrote in Arabic.
    """
    # English, because Arabic is the model default. Written with Arabic first, this passed
    # while the assignment was deleted — the field simply kept its default and agreed. A test
    # of a defaulted field has to use the value that is not the default.
    #
    # The language is set the way a real visitor sets it. `translation.override` in the test
    # does not reach the view: LocaleMiddleware activates its own language from the request
    # and overwrites it, so the override was in force everywhere except where it mattered.
    client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"

    submit(client, category, email="english@example.com")

    assert ContactDetail.objects.get(value="english@example.com").contact.preferred_language == "en"


def test_it_now_offers_categories_in_the_readers_language(client, department, branch):
    """A change to this form, and a deliberate one.

    FR-025 protects the form's behaviour, not its defects: it has offered English category
    names to Arabic visitors since the MVP, on the one screen anonymous Arabic-speaking
    customers actually meet. Everything else here is unchanged, which the rest of this file
    asserts.
    """
    from apps.tickets.models import Category

    Category.objects.create(name="Billing", name_ar="الفوترة", department=department)
    client.cookies[settings.LANGUAGE_COOKIE_NAME] = "ar"

    body = client.get(reverse("intake:form")).content.decode()

    assert "الفوترة" in body
    assert ">Billing<" not in body
