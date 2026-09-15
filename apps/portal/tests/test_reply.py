"""
T056-T061. A customer replies from the portal (FR-020 to FR-024).

This is the first door in this feature through which text a stranger wrote enters the system,
and the first time the portal writes anything at all. Two things follow.

The reply must be indistinguishable from an emailed one in every way that matters to the desk
— same author attribution, same effect on the ticket's state — and distinguishable in exactly
one way that matters to an agent reading it: it says it came from the portal.

And the state change must not be reimplemented here. `reopen_for_customer_reply` already
decides what a customer's reply does to a ticket, for the email channel. A second copy of that
rule is a second answer to "what happens when a customer replies", and the two drift on the
day somebody changes one of them.
"""

import pytest
from django.urls import reverse

from apps.tickets.models import Message, Ticket

pytestmark = pytest.mark.django_db


def reply(client, ticket, body="Still nothing has arrived."):
    return client.post(reverse("portal:reply", args=[ticket.reference]), {"body": body})


def test_a_reply_joins_the_conversation(customer_client, customer_ticket):
    """FR-020, scenario 1."""
    reply(customer_client, customer_ticket)

    message = customer_ticket.messages.get()
    assert message.body == "Still nothing has arrived."
    assert message.direction == Message.Direction.INBOUND
    assert message.visibility == Message.Visibility.PUBLIC


def test_it_is_not_attributed_to_a_member_of_staff(customer_client, customer_ticket):
    """`author` is the STAFF author. A customer is not a User, so the field stays null —
    exactly as it does for an emailed reply (apps/messaging/services/inbound.py).

    Putting anything else there would mean the audit trail claims an agent wrote what a
    customer wrote.
    """
    reply(customer_client, customer_ticket)

    assert customer_ticket.messages.get().author is None


def test_it_is_marked_as_coming_from_the_portal(customer_client, customer_ticket):
    """FR-021, scenario 2. The one way it should differ from an emailed reply.

    An agent reading a thread needs to know whether the customer is in the portal — because if
    they are, the agent can expect them to see the answer there, and if they are not, the
    answer has to survive an email client.
    """
    reply(customer_client, customer_ticket)

    assert customer_ticket.messages.get().channel == Ticket.Channel.PORTAL


def test_the_agent_sees_it_on_the_ticket(agent_client, customer_client, customer_ticket, agent):
    """Scenario 1's second half. The reply is no use if it lands somewhere the desk does not
    look."""
    reply(customer_client, customer_ticket)

    body = agent_client.get(
        reverse("tickets:detail", args=[customer_ticket.reference])
    ).content.decode()

    assert "Still nothing has arrived." in body


def test_a_reply_stops_a_request_waiting_on_the_customer(customer_client, customer_ticket):
    """FR-022, scenario 3."""
    customer_ticket.status = Ticket.Status.PENDING_CUSTOMER
    customer_ticket.save(update_fields=["status"])

    reply(customer_client, customer_ticket)

    customer_ticket.refresh_from_db()
    assert customer_ticket.status == Ticket.Status.OPEN


def test_a_reply_reopens_a_resolved_request(customer_client, customer_ticket):
    """Scenario 4. The edge case the MVP named explicitly: a customer's message must never be
    lost behind a finished ticket."""
    customer_ticket.status = Ticket.Status.RESOLVED
    customer_ticket.save(update_fields=["status"])

    reply(customer_client, customer_ticket)

    customer_ticket.refresh_from_db()
    assert customer_ticket.status == Ticket.Status.OPEN


def test_a_reply_reopens_a_closed_request(customer_client, customer_ticket):
    customer_ticket.status = Ticket.Status.CLOSED
    customer_ticket.save(update_fields=["status"])

    reply(customer_client, customer_ticket)

    customer_ticket.refresh_from_db()
    assert customer_ticket.status == Ticket.Status.OPEN


def test_an_open_request_stays_open(customer_client, customer_ticket):
    """So the rule cannot be satisfied by moving every ticket to OPEN on every reply — which
    would pass the three tests above and would quietly undo an agent's status changes."""
    customer_ticket.status = Ticket.Status.OPEN
    customer_ticket.save(update_fields=["status"])

    reply(customer_client, customer_ticket)

    customer_ticket.refresh_from_db()
    assert customer_ticket.status == Ticket.Status.OPEN


# --- what must be refused (FR-024, scenarios 6 and 7) ---


def test_an_empty_reply_is_refused_and_writes_nothing(customer_client, customer_ticket):
    response = reply(customer_client, customer_ticket, body="   ")

    assert response.status_code == 200
    assert customer_ticket.messages.count() == 0
    assert response.context["form"].errors.get("body")


def test_an_over_long_reply_is_refused_and_writes_nothing(
    customer_client, customer_ticket, settings
):
    settings.PORTAL_MESSAGE_MAX_LENGTH = 50

    response = reply(customer_client, customer_ticket, body="x" * 51)

    assert customer_ticket.messages.count() == 0
    assert response.context["form"].errors.get("body")


def test_the_refusal_says_which_problem_it_was(customer_client, customer_ticket, settings):
    """FR-024 asks for a reason "that says which". "Invalid" leaves somebody who wrote four
    paragraphs guessing whether to shorten them or retype them.

    `list(...)` around both sides, and not for tidiness. `django.forms.utils.ErrorList`
    overrides `__eq__` and inherits `__ne__` from its base, so the two disagree: for two
    genuinely different error lists, `a == b` is False AND `a != b` is False. Written the
    obvious way this assertion can never pass, whatever the code does.
    """
    settings.PORTAL_MESSAGE_MAX_LENGTH = 50

    empty = reply(customer_client, customer_ticket, body="")
    too_long = reply(customer_client, customer_ticket, body="x" * 51)

    assert list(empty.context["form"].errors["body"]) != list(
        too_long.context["form"].errors["body"]
    )


def test_a_refused_reply_is_given_back_to_the_customer(customer_client, customer_ticket, settings):
    """Scenario 5 says nothing they wrote is lost, and the same courtesy applies to a
    validation refusal — somebody who has just written four paragraphs and is handed an empty
    box has been punished for a typo."""
    settings.PORTAL_MESSAGE_MAX_LENGTH = 50
    written = "x" * 51

    body = reply(customer_client, customer_ticket, body=written).content.decode()

    assert written in body


def test_a_reply_to_somebody_elses_request_is_refused(customer_client, ticket):
    """Scenario 7. Not found, and nothing written — checked separately, because a view that
    writes first and refuses afterwards passes any test that only looks at the status."""
    response = customer_client.post(
        reverse("portal:reply", args=[ticket.reference]), {"body": "Let me in."}
    )

    assert response.status_code == 404
    assert ticket.messages.count() == 0


def test_a_reply_to_a_reference_that_does_not_exist_is_refused_the_same_way(
    customer_client, ticket
):
    from apps.portal.tests.identity import comparable

    someone_elses = customer_client.post(
        reverse("portal:reply", args=[ticket.reference]), {"body": "Let me in."}
    )
    never_issued = customer_client.post(
        reverse("portal:reply", args=["AZM-2099-999999"]), {"body": "Let me in."}
    )

    assert someone_elses.status_code == never_issued.status_code == 404
    assert comparable(someone_elses, ticket.reference) == comparable(
        never_issued, "AZM-2099-999999"
    )


def test_replying_needs_a_post(customer_client, customer_ticket):
    assert (
        customer_client.get(reverse("portal:reply", args=[customer_ticket.reference])).status_code
        == 405
    )


def test_an_unconfirmed_account_cannot_reply(client, customer, customer_ticket):
    from django.conf import settings

    from apps.portal.auth import CUSTOMER_SESSION_KEY

    customer.email_confirmed_at = None
    customer.save(update_fields=["email_confirmed_at"])
    session = client.session
    session[CUSTOMER_SESSION_KEY] = customer.pk
    session.save()
    client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

    reply(client, customer_ticket)

    assert customer_ticket.messages.count() == 0


def test_a_reply_appears_on_the_customers_own_page(customer_client, customer_ticket):
    reply(customer_client, customer_ticket)

    body = customer_client.get(
        reverse("portal:request", args=[customer_ticket.reference])
    ).content.decode()

    assert "Still nothing has arrived." in body


def test_the_over_long_message_reaches_an_arabic_customer_in_arabic(
    customer_client, customer, customer_ticket, settings
):
    """The plural message, end to end, in the language that has six forms.

    Worth asserting through the view rather than trusting the catalog. gettext merged this
    message onto an unrelated one about file sizes, so all six Arabic forms arrived carrying
    `%(size)s` — a placeholder this message never supplies. Accepted as-is that is not bad
    wording, it is a KeyError at render time, in Arabic only, on the error path that only
    fires when somebody writes too much.
    """
    settings.PORTAL_MESSAGE_MAX_LENGTH = 50
    customer.language = "ar"
    customer.save(update_fields=["language"])

    response = reply(customer_client, customer_ticket, body="x" * 60)
    message = str(response.context["form"].errors["body"][0])

    assert "50" in message, "The limit did not make it into the message."
    assert "الحد الأقصى" in message, f"An Arabic customer was shown: {message}"


def test_the_empty_message_is_the_one_this_product_chose(customer_client, customer_ticket):
    """Not Django's default.

    The message was first written as a check inside `clean_body`, where it could never run:
    `required` is evaluated before any `clean_<field>` method, so the branch was dead and the
    customer read "This field is required." The test that appeared to cover it only asserted
    that the empty and over-long messages DIFFER, which they did — one of them was just not
    ours.
    """
    response = reply(customer_client, customer_ticket, body="")
    message = str(response.context["form"].errors["body"][0])

    assert (
        message == "Write something before sending."
    ), f'The empty-reply message is "{message}", which is not the one this product wrote.'


def test_a_whitespace_only_reply_gets_the_same_message(customer_client, customer_ticket):
    """`strip=True` turns "   " into "", so it lands on the same path — asserted rather than
    assumed, because if stripping ever changed this would silently start saving blank
    messages onto tickets."""
    response = reply(customer_client, customer_ticket, body="  \n  ")

    assert customer_ticket.messages.count() == 0
    assert str(response.context["form"].errors["body"][0]) == "Write something before sending."
