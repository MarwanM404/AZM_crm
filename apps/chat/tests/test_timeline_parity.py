"""
A chat ticket is a ticket (T070, FR-030).

The point of persisting the transcript onto a ticket is that afterwards nothing has to know it
came from chat. It appears in the queue, it can be filtered, assigned, replied to and
resolved, and it sits in the customer's history beside the emails and the phone calls in one
chronological order. A customer's history is not per-channel; a supervisor asking "what has
happened with this account" must not have to visit two places.

`origin_channel` is therefore a label, not a fork. These tests exist to stop it becoming one.
"""

import pytest
from django.urls import reverse

from apps.chat.services import messaging
from apps.chat.services.redis_client import reset_for_tests
from apps.customers.models import Organization
from apps.tickets.models import Ticket

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clean():
    reset_for_tests()
    yield
    reset_for_tests()


@pytest.fixture
def chat_ticket(assigned_conversation, agent):
    messaging.visitor_message(assigned_conversation, "Asked over chat")
    messaging.agent_message(assigned_conversation, agent, "Answered over chat")
    return assigned_conversation.ticket


def test_it_appears_in_the_same_queue_as_every_other_ticket(agent_client, chat_ticket, ticket):
    body = agent_client.get(reverse("tickets:queue")).content.decode()

    assert chat_ticket.reference in body
    assert ticket.reference in body


def test_it_is_reachable_at_the_ordinary_ticket_detail_url(agent_client, chat_ticket):
    response = agent_client.get(reverse("tickets:detail", args=[chat_ticket.reference]))

    assert response.status_code == 200
    assert "Asked over chat" in response.content.decode()


def test_the_transcript_is_visible_on_the_ticket_not_only_in_the_chat_console(
    agent_client, chat_ticket
):
    """The transcript has to be readable by someone who never opens the chat console — that
    is what makes it a record rather than a log."""
    body = agent_client.get(
        reverse("tickets:detail", args=[chat_ticket.reference])
    ).content.decode()

    assert "Asked over chat" in body
    assert "Answered over chat" in body


def test_it_can_be_worked_like_any_other_ticket(agent_client, chat_ticket):
    """Status transitions come from apps/tickets — chat reuses them rather than owning a
    parallel lifecycle."""
    response = agent_client.post(
        reverse("tickets:status", args=[chat_ticket.reference]),
        {"status": Ticket.Status.OPEN},
    )
    chat_ticket.refresh_from_db()

    assert response.status_code in (200, 204, 302)
    assert chat_ticket.status == Ticket.Status.OPEN


def test_a_reply_typed_on_the_ticket_joins_the_same_transcript(agent_client, chat_ticket):
    agent_client.post(
        reverse("tickets:reply", args=[chat_ticket.reference]),
        {"body": "Following up by email"},
    )

    bodies = list(chat_ticket.messages.order_by("created_at").values_list("body", flat=True))
    assert bodies == ["Asked over chat", "Answered over chat", "Following up by email"]


def test_it_sits_in_the_customer_history_beside_other_channels(
    agent_client, chat_ticket, department, branch, category, contact
):
    """One timeline, ordered by time, not one tab per channel."""
    organization = Organization.objects.create(
        name="Najd Trading", department=department, branch=branch
    )
    contact.organization = organization
    contact.save(update_fields=["organization"])
    email_ticket = Ticket.objects.create(
        contact=contact,
        organization=organization,
        subject="Invoice query",
        description="",
        category=category,
        origin_channel=Ticket.Channel.EMAIL,
        department=department,
        branch=branch,
    )
    chat_ticket.organization = organization
    chat_ticket.save(update_fields=["organization"])

    body = agent_client.get(reverse("customers:detail", args=[organization.pk])).content.decode()

    assert chat_ticket.reference in body
    assert email_ticket.reference in body


def test_an_internal_note_on_a_chat_ticket_obeys_the_same_boundary(
    agent_client, chat_ticket, agent
):
    """FR-014/FR-015 is one boundary for the whole system. Chat reuses it; a second
    implementation is a second thing to get wrong."""
    from apps.tickets.models import Message
    from apps.tickets.services.visibility import public_messages_for

    Message.objects.create(
        ticket=chat_ticket,
        author=agent,
        direction=Message.Direction.OUTBOUND,
        visibility=Message.Visibility.INTERNAL,
        channel=Ticket.Channel.CHAT,
        body="Internal: check the refund policy",
    )

    visible = list(public_messages_for(chat_ticket).values_list("body", flat=True))
    assert "Internal: check the refund policy" not in visible
