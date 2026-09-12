"""
The conversation as a permanent record (T065, T066, T067, T071).

The transcript is not written at the end — messages land on the ticket as they are sent
(research.md #6). That matters for what these tests assert: a conversation that ends badly,
by a crash or a closed laptop, still has everything said up to that point, because there was
never a moment when the transcript existed only in memory.
"""

import pytest
from django.urls import reverse

from apps.chat.models import Conversation
from apps.chat.services import lifecycle, messaging, presence
from apps.chat.services.redis_client import reset_for_tests
from apps.tickets.models import Message, Ticket

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clean():
    reset_for_tests()
    yield
    reset_for_tests()


def test_a_ticket_exists_from_the_moment_the_conversation_starts(client, agent, category, branch):
    """FR-040. A transcript can never be orphaned by an unexpected ending, because there is
    never a point at which the conversation has nowhere to be written."""
    presence.go_online(agent.pk, capacity=3)
    client.post(
        reverse("chat:start"),
        {
            "full_name": "Sara",
            "email": "sara@example.com",
            "subject": "Help",
            "category": category.pk,
        },
    )

    conversation = Conversation.objects.get()
    assert conversation.ticket_id is not None
    assert conversation.ticket.origin_channel == Ticket.Channel.CHAT


def test_the_visitor_is_given_no_reference_until_it_ends(client, agent, category, branch):
    """FR-040: the agent may attach the conversation to an existing ticket in between, and a
    reference handed out at the start could be one the customer can no longer use."""
    presence.go_online(agent.pk, capacity=3)
    body = client.post(
        reverse("chat:start"),
        {
            "full_name": "Sara",
            "email": "sara@example.com",
            "subject": "Help",
            "category": category.pk,
        },
    ).json()

    assert "reference" not in body


def test_every_message_is_on_the_ticket_in_order(assigned_conversation, agent):
    messaging.visitor_message(assigned_conversation, "My order never arrived")
    messaging.agent_message(assigned_conversation, agent, "Let me check that")
    messaging.visitor_message(assigned_conversation, "Thank you")

    bodies = list(
        assigned_conversation.ticket.messages.order_by("created_at").values_list("body", flat=True)
    )
    assert bodies == ["My order never arrived", "Let me check that", "Thank you"]


def test_each_message_is_attributed_and_timestamped(assigned_conversation, agent):
    messaging.visitor_message(assigned_conversation, "From the customer")
    messaging.agent_message(assigned_conversation, agent, "From the agent")

    from_customer, from_agent = assigned_conversation.ticket.messages.order_by("created_at")

    assert from_customer.author is None and from_customer.direction == Message.Direction.INBOUND
    assert from_agent.author_id == agent.pk
    assert from_customer.created_at is not None and from_agent.created_at is not None
    assert from_customer.created_at <= from_agent.created_at


def test_a_conversation_ended_by_a_disconnection_keeps_what_was_said(assigned_conversation, agent):
    """SC-003 puts transcript completeness at 100% *including* conversations ended by a
    disconnection — which is only achievable because nothing waits for a clean ending."""
    messaging.visitor_message(assigned_conversation, "Said before the line dropped")

    lifecycle.end(assigned_conversation, reason=Conversation.EndReason.VISITOR_DISCONNECTED)

    assert assigned_conversation.ticket.messages.filter(
        body="Said before the line dropped"
    ).exists()


def test_ending_records_why(assigned_conversation, agent):
    """ "The customer left" and "the agent closed it" are different facts about the same ended
    conversation, and only one of them is a service problem."""
    lifecycle.end(assigned_conversation, reason=Conversation.EndReason.ENDED_BY_VISITOR)
    assigned_conversation.refresh_from_db()

    assert assigned_conversation.state == Conversation.State.ENDED
    assert assigned_conversation.end_reason == Conversation.EndReason.ENDED_BY_VISITOR
    assert assigned_conversation.ended_at is not None


def test_ending_twice_does_not_change_the_first_ending(assigned_conversation, agent):
    """A visitor closing the tab as the agent clicks end must not produce two endings, and
    whichever arrives second must not overwrite the first."""
    lifecycle.end(assigned_conversation, reason=Conversation.EndReason.ENDED_BY_VISITOR)
    first_ended_at = assigned_conversation.ended_at

    lifecycle.end(
        assigned_conversation, reason=Conversation.EndReason.ENDED_BY_AGENT, ended_by=agent
    )
    assigned_conversation.refresh_from_db()

    assert assigned_conversation.end_reason == Conversation.EndReason.ENDED_BY_VISITOR
    assert assigned_conversation.ended_at == first_ended_at


def test_an_unresolved_conversation_leaves_its_ticket_open(assigned_conversation, agent):
    """FR-029: ending a chat is not the same as solving the problem."""
    lifecycle.end(
        assigned_conversation, reason=Conversation.EndReason.ENDED_BY_AGENT, ended_by=agent
    )
    assigned_conversation.ticket.refresh_from_db()

    assert assigned_conversation.ticket.status != Ticket.Status.RESOLVED


def test_resolving_at_the_end_resolves_the_ticket(assigned_conversation, agent):
    lifecycle.end(
        assigned_conversation,
        reason=Conversation.EndReason.RESOLVED,
        ended_by=agent,
        resolve=True,
    )
    assigned_conversation.ticket.refresh_from_db()

    assert assigned_conversation.ticket.status == Ticket.Status.RESOLVED
