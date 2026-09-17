"""
A customer can find out the portal exists.

Spec 004 built the portal and linked to it from nowhere. Every route worked, every screen was
correct, and no template outside `templates/portal/` mentioned it — so the only people who
could reach it were the ones who already knew the URL, which is to say staff.

That is not a gap in the specification; it was never in scope there. It is a gap in the
product, and the places to close it are the three moments a customer has just been given a
reference and is wondering how to follow it: the page after they submit a request, the message
confirming it, and every reply that follows.

The email assertions insist on an ABSOLUTE link. A relative one is meaningless in a mail
client — there is no page it is relative to — and it is the kind of mistake that looks right in
a test asserting the path is present.
"""

import pytest
from django.core import mail
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_the_page_after_submitting_offers_an_account(client, category, branch):
    """The moment a customer most wants to know they can follow this without writing in."""
    import time

    client.post(
        reverse("intake:form"),
        {
            "full_name": "Sara Ahmed",
            "email": "sara@example.com",
            "phone": "",
            "category": category.pk,
            "subject": "Nothing arrived",
            "description": "...",
            "company_website": "",
            "rendered_at": time.time() - 10,
        },
        follow=True,
    )
    from apps.tickets.models import Ticket

    body = client.get(
        reverse("intake:submitted", args=[Ticket.objects.get().reference])
    ).content.decode()

    assert reverse("portal:register") in body


def test_the_confirmation_email_carries_an_absolute_portal_link(client, category, branch, settings):
    import time

    settings.PORTAL_BASE_URL = "https://support.example.com"
    mail.outbox.clear()
    client.post(
        reverse("intake:form"),
        {
            "full_name": "Sara Ahmed",
            "email": "sara@example.com",
            "phone": "",
            "category": category.pk,
            "subject": "Nothing arrived",
            "description": "...",
            "company_website": "",
            "rendered_at": time.time() - 10,
        },
    )

    body = mail.outbox[0].body
    assert (
        "https://support.example.com/portal/register/" in body
    ), f"no absolute portal link in the confirmation message:\n{body}"


def test_the_reply_email_carries_an_absolute_portal_link(agent_client, ticket, settings):
    settings.PORTAL_BASE_URL = "https://support.example.com"
    mail.outbox.clear()

    agent_client.post(
        reverse("tickets:reply", args=[ticket.reference]),
        {"body": "We are looking into it."},
    )

    body = mail.outbox[0].body
    assert (
        "https://support.example.com/portal/" in body
    ), f"no absolute portal link in the reply:\n{body}"


def test_an_arabic_customer_is_offered_it_in_arabic(client, category, branch, settings):
    """The link is useless to somebody who cannot read the sentence around it."""
    settings.PORTAL_BASE_URL = "https://support.example.com"
    client.cookies[settings.LANGUAGE_COOKIE_NAME] = "ar"
    mail.outbox.clear()

    import time

    client.post(
        reverse("intake:form"),
        {
            "full_name": "سارة أحمد",
            "email": "sara.ar@example.com",
            "phone": "",
            "category": category.pk,
            "subject": "لم يصل شيء",
            "description": "...",
            "company_website": "",
            "rendered_at": time.time() - 10,
        },
    )

    body = mail.outbox[0].body
    assert "https://support.example.com/portal/register/" in body
    assert (
        "بوابة" in body or "حساب" in body
    ), f"the Arabic confirmation offers the portal in English, or not at all:\n{body}"


def test_the_link_does_not_disclose_anything(client, category, branch, settings):
    """It goes to the registration screen, not to the ticket.

    A link that opened the request directly would be a way into somebody's data from a
    forwarded email, and this message is forwarded constantly — to a colleague, to a manager,
    into a shared mailbox.
    """
    import time

    settings.PORTAL_BASE_URL = "https://support.example.com"
    mail.outbox.clear()
    client.post(
        reverse("intake:form"),
        {
            "full_name": "Sara Ahmed",
            "email": "sara@example.com",
            "phone": "",
            "category": category.pk,
            "subject": "Nothing arrived",
            "description": "...",
            "company_website": "",
            "rendered_at": time.time() - 10,
        },
    )
    from apps.tickets.models import Ticket

    reference = Ticket.objects.get().reference
    body = mail.outbox[0].body

    assert (
        f"/portal/requests/{reference}" not in body
    ), "the message links straight to the request, so anyone it is forwarded to can open it"


def test_the_end_of_a_chat_offers_it_too(client, agent):
    """The third moment a customer is handed a reference and left holding it.

    A chat that ends with "your reference is AZM-…" and no way to look it up is the same dead
    end as the confirmation email was: the customer has an identifier and nowhere to type it.

    An agent has to be online for the chat UI to exist at all — `{% if available %}` gates the
    whole thing, and without this the page renders the "nobody is available" branch and the
    assertion would be about a screen that is not the one under test.
    """
    from apps.chat.services import presence

    presence.go_online(agent.pk, capacity=3)

    body = client.get(reverse("chat:widget")).content.decode()

    assert reverse("portal:register") in body, (
        "the chat widget never mentions the portal, so a customer who has just been given a "
        "reference has nowhere to follow it"
    )
