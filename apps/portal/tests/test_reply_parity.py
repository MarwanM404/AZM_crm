"""
T062. A portal reply and an emailed reply do the same thing (FR-022).

The other tests in this feature assert what a portal reply does. This one asserts that it does
the same as the channel that already existed — which is a different and more durable claim,
because it keeps holding when somebody changes the rule.

The failure it guards against is slow. Nothing breaks on the day the portal's copy of the
state logic is written; it breaks months later when a rule changes in one place, and the
symptom is a customer whose emailed reply reopens their ticket and whose portal reply does
not. Nobody reports that as a bug — they report that the portal does not work.

Both paths are driven end to end rather than compared at the service level, because the
service is the part they are supposed to share. Comparing there would pass even if the portal
view never called it.
"""

import pytest

from apps.messaging.services.inbound import ingest
from apps.tickets.models import Message, Ticket

pytestmark = pytest.mark.django_db

STATES = [
    Ticket.Status.NEW,
    Ticket.Status.OPEN,
    Ticket.Status.PENDING_CUSTOMER,
    Ticket.Status.RESOLVED,
    Ticket.Status.CLOSED,
]


def _at(ticket, status):
    ticket.status = status
    ticket.save(update_fields=["status"])
    return ticket


def _emailed_reply(ticket, sender, department, branch):
    """The real inbound path, matched the way a real reply matches: the plus-address on the
    To line that outbound mail sets as its Reply-To."""
    ingest(
        {
            "from": sender,
            "to": f"support+{ticket.reference}@example.com",
            "subject": f"Re: [{ticket.reference}] {ticket.subject}",
            "body": "Still nothing has arrived.",
        },
        department,
        branch,
    )


@pytest.mark.parametrize("status", STATES)
def test_the_two_channels_leave_the_request_in_the_same_state(
    customer_client, customer, customer_ticket, status, department, branch
):
    """Every status the product has, not a chosen few.

    Parametrised over `Ticket.Status` itself rather than a literal list would be better still;
    it is written out so that a status added later fails this test loudly and somebody has to
    decide what a customer's reply does to it.
    """
    from django.urls import reverse

    _at(customer_ticket, status)
    customer_client.post(
        reverse("portal:reply", args=[customer_ticket.reference]),
        {"body": "Still nothing has arrived."},
    )
    customer_ticket.refresh_from_db()
    from_portal = customer_ticket.status

    _at(customer_ticket, status)
    _emailed_reply(customer_ticket, customer.email, department, branch)
    customer_ticket.refresh_from_db()
    from_email = customer_ticket.status

    assert from_portal == from_email, (
        f"A request at {status} ends at {from_portal} after a portal reply and at {from_email} "
        "after an emailed one. The two channels have drifted."
    )


def test_every_status_is_covered():
    """The list above is written out, so it can fall behind the model.

    A status added to `Ticket.Status` without being added here would leave the newest and
    least-understood state as the one nobody checked.
    """
    assert set(STATES) == set(Ticket.Status.values), (
        "Ticket.Status has changed. Decide what a customer's reply does to the new status and "
        "add it to STATES."
    )


def test_the_two_channels_attribute_the_message_the_same_way(
    customer_client, customer, customer_ticket, department, branch
):
    """Same author, same direction, same visibility. Different channel, and only that."""
    from django.urls import reverse

    customer_client.post(
        reverse("portal:reply", args=[customer_ticket.reference]),
        {"body": "From the portal."},
    )
    _emailed_reply(customer_ticket, customer.email, department, branch)

    portal, emailed = customer_ticket.messages.order_by("created_at")

    assert portal.author == emailed.author is None
    assert portal.direction == emailed.direction == Message.Direction.INBOUND
    assert portal.visibility == emailed.visibility == Message.Visibility.PUBLIC
    assert portal.channel == Ticket.Channel.PORTAL
    assert emailed.channel == Ticket.Channel.EMAIL


def test_the_portal_does_not_reimplement_the_state_rule():
    """A source check, because the tests above would pass against a faithful copy — and a
    faithful copy is exactly what drifts.

    `reopen_for_customer_reply` is the one place this product decides what a customer's reply
    does to a ticket. The portal must call it rather than know it.
    """
    from pathlib import Path

    portal = Path(__file__).resolve().parent.parent
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in portal.rglob("*.py")
        if "tests" not in path.parts
    )

    assert "reopen_for_customer_reply" in source, (
        "The portal does not call reopen_for_customer_reply. If the state change is decided "
        "here instead, this product has two answers to what a customer's reply does."
    )
    for status in ("RESOLVED", "PENDING_CUSTOMER"):
        assert f"Status.{status}" not in source, (
            f"The portal names Ticket.Status.{status} in its own code, which means it is "
            "deciding the state transition rather than delegating it."
        )
