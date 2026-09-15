"""
T046-T049. Opening one request (FR-015 to FR-019).

Two rules meet here and they are the two this feature is most likely to get wrong quietly.

The internal boundary (FR-016) has existed since the MVP and is swept across every
customer-facing template. The portal adds a screen that renders a ticket's conversation, which
is precisely the shape that leaks: the safe query and the unsafe one differ by one filter, and
the unsafe one is shorter.

The not-found rule (FR-017) is about the status code being information. A 403 on somebody
else's reference says "that reference exists"; enough of those and an attacker has a map of
the desk's volume. So the refusal must be indistinguishable from a reference that was never
issued — same status, same body.
"""

import pytest
from django.urls import reverse

from apps.tickets.models import Message, Ticket

pytestmark = pytest.mark.django_db

SECRET = "INTERNAL-ONLY-DO-NOT-SHOW-THE-CUSTOMER"


def detail(client, reference):
    return client.get(reverse("portal:request", args=[reference]))


@pytest.fixture
def conversation(customer_ticket, agent):
    """A request with both sides of the boundary on it."""
    Message.objects.create(
        ticket=customer_ticket,
        direction=Message.Direction.INBOUND,
        visibility=Message.Visibility.PUBLIC,
        channel=Ticket.Channel.EMAIL,
        body="Any news on this?",
    )
    Message.objects.create(
        ticket=customer_ticket,
        author=agent,
        direction=Message.Direction.OUTBOUND,
        visibility=Message.Visibility.PUBLIC,
        channel=Ticket.Channel.EMAIL,
        body="We are chasing the courier and will update you today.",
    )
    Message.objects.create(
        ticket=customer_ticket,
        author=agent,
        direction=Message.Direction.OUTBOUND,
        visibility=Message.Visibility.INTERNAL,
        channel=Ticket.Channel.EMAIL,
        body=SECRET,
    )
    return customer_ticket


def test_the_conversation_appears_in_order(customer_client, conversation):
    """T046, FR-015."""
    body = detail(customer_client, conversation.reference).content.decode()

    assert "Any news on this?" in body
    assert "We are chasing the courier" in body
    assert body.index("Any news on this?") < body.index("We are chasing the courier")


def test_the_original_request_is_shown(customer_client, conversation):
    """The customer's own opening words.

    They live on `Ticket.description` rather than as a `Message`, so a conversation built only
    from messages begins in the middle — the customer reads the reply to a question the page
    never shows them asking. It is their own text, so showing it discloses nothing.
    """
    body = detail(customer_client, conversation.reference).content.decode()

    assert conversation.description in body


def test_an_internal_note_is_absent_from_the_page(customer_client, conversation):
    """T047, FR-016, scenario 4."""
    body = detail(customer_client, conversation.reference).content.decode()

    assert SECRET not in body


def test_an_internal_note_is_absent_from_the_context_too(customer_client, conversation):
    """Not only from the rendered page.

    A note that reaches the template and is merely not printed is one `{{ }}` away from being
    printed, and the person who adds that `{{ }}` will be looking at a variable the view
    handed them and will reasonably assume it is safe to show.
    """
    response = detail(customer_client, conversation.reference)

    for message in response.context["public_messages"]:
        assert message.visibility == Message.Visibility.PUBLIC
        assert SECRET not in message.body


def test_somebody_elses_request_is_refused_exactly_like_one_that_does_not_exist(
    customer_client, ticket
):
    """T048, FR-017, scenario 5. Compared as text, not just as a status code.

    The status code is the obvious channel and not the only one: a page that says "no such
    request TCK-2026-0007" for an invented reference and "not found" for a real one has
    answered the question just as clearly.
    """
    from apps.portal.tests.identity import comparable

    someone_elses = detail(customer_client, ticket.reference)
    never_issued = detail(customer_client, "TCK-2099-9999")

    assert someone_elses.status_code == 404
    assert never_issued.status_code == 404
    assert comparable(someone_elses, ticket.reference) == comparable(never_issued, "TCK-2099-9999")


def test_it_is_not_forbidden(customer_client, ticket):
    """Stated separately from the test above because 403 is what a framework gives you for
    free, and 404 is what this product requires (MVP FR-024)."""
    assert detail(customer_client, ticket.reference).status_code != 403


def test_a_soft_deleted_request_is_not_found(customer_client, customer_ticket, agent):
    customer_ticket.soft_delete(by=agent)

    assert detail(customer_client, customer_ticket.reference).status_code == 404


def test_resolved_and_closed_requests_stay_readable(customer_client, conversation):
    """T049, FR-019, scenario 7."""
    for status in (Ticket.Status.RESOLVED, Ticket.Status.CLOSED):
        conversation.status = status
        conversation.save(update_fields=["status"])

        response = detail(customer_client, conversation.reference)

        assert response.status_code == 200, f"A {status} request became unreadable."
        assert "We are chasing the courier" in response.content.decode()


def test_an_unconfirmed_account_cannot_open_a_request(client, customer, customer_ticket):
    """The address on the account matches the ticket's contact — and that is exactly the case
    confirmation exists to stop. Anyone can type a stranger's address into a public form.

    The confirmation is taken off the account that already holds this address, rather than a
    second account being given it: one address is one account, so the scenario is "this
    customer has not confirmed yet", not "two accounts claim the same address".
    """

    from apps.portal.tests.sessions import sign_in as start_session

    customer.email_confirmed_at = None
    customer.save(update_fields=["email_confirmed_at"])

    start_session(client, customer)

    assert detail(client, customer_ticket.reference).status_code != 200


def test_the_detail_carries_a_way_back(customer_client, conversation):
    body = detail(customer_client, conversation.reference).content.decode()

    assert reverse("portal:home") in body


def test_the_template_never_receives_the_ticket(customer_client, conversation):
    """The mechanism, not the symptom.

    Filtering the messages and handing over the ticket anyway passes every boundary test in
    this file — because the template as written does not reach for `ticket.messages`. The
    next person to edit it would have a ticket object in scope and no reason to suspect it.
    `customer_facing_context` exists so that the reach is impossible rather than merely
    unmade, and tests/test_internal_visibility.py asserts the same thing about every other
    customer-facing screen.
    """
    response = detail(customer_client, conversation.reference)

    assert "ticket" not in response.context, (
        "The detail template is handed the ticket, so a later edit can walk to "
        "ticket.messages and print an internal note."
    )
    for value in response.context["public_messages"]:
        assert not hasattr(value, "messages")
