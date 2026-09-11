"""
FR-015: no message marked INTERNAL may appear in ANY customer-facing output.

This is the cross-cutting invariant the roadmap pulled forward into the MVP (M8a) so that
live chat's supervisor-whisper feature lands on prepared ground. It enumerates every
customer-facing path that exists and asserts the internal note is absent from all of them —
and asserts the single filter that every such path must route through.
"""

import pytest
from django.core import mail
from django.urls import reverse

from apps.tickets.models import Message
from apps.tickets.services.visibility import public_messages_for, staff_messages_for

SECRET = "CARRIER-SIGNATURE-DOES-NOT-MATCH-INTERNAL-ONLY"


@pytest.fixture
def ticket_with_both(ticket, agent):
    Message.objects.create(
        ticket=ticket,
        author=agent,
        direction=Message.Direction.OUTBOUND,
        visibility=Message.Visibility.PUBLIC,
        channel=ticket.origin_channel,
        body="Public: we are investigating with the carrier.",
    )
    Message.objects.create(
        ticket=ticket,
        author=agent,
        direction=Message.Direction.OUTBOUND,
        visibility=Message.Visibility.INTERNAL,
        channel=ticket.origin_channel,
        body=SECRET,
    )
    return ticket


@pytest.mark.django_db
def test_public_filter_excludes_internal(ticket_with_both):
    bodies = [m.body for m in public_messages_for(ticket_with_both)]
    assert SECRET not in bodies
    assert len(bodies) == 1


@pytest.mark.django_db
def test_staff_view_includes_internal(ticket_with_both):
    bodies = [m.body for m in staff_messages_for(ticket_with_both)]
    assert SECRET in bodies


@pytest.mark.django_db
def test_outbound_email_never_carries_an_internal_message(agent_client, ticket_with_both):
    mail.outbox.clear()
    agent_client.post(
        reverse("tickets:reply", args=[ticket_with_both.reference]),
        {"body": "Here is the update we promised."},
    )
    assert len(mail.outbox) == 1
    sent = mail.outbox[0]
    assert SECRET not in sent.body
    assert SECRET not in sent.subject
    for content, _mime in getattr(sent, "alternatives", []):
        assert SECRET not in content


@pytest.mark.django_db
def test_send_task_refuses_an_internal_message_outright(ticket_with_both):
    """Defence in depth: even called directly with an internal message id, the send path
    must not deliver it."""
    from apps.messaging.tasks import send_ticket_reply_email

    internal = ticket_with_both.messages.get(visibility=Message.Visibility.INTERNAL)
    mail.outbox.clear()
    send_ticket_reply_email(message_id=internal.pk)
    assert mail.outbox == []


@pytest.mark.django_db
def test_public_confirmation_page_carries_no_messages_at_all(client, ticket_with_both):
    response = client.get(reverse("intake:submitted", args=[ticket_with_both.reference]))
    body = response.content.decode()
    assert SECRET not in body
    assert "Public: we are investigating" not in body
