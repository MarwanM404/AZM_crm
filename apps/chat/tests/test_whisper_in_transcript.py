"""
FR-025: the note is on the ticket for staff, and in no customer-facing output (T092).

The transcript is the permanent record of the conversation, and a supervisor's coaching is
part of what happened — a complaint reviewed six months later should show that the agent was
told to check the policy. So the note is kept, on the same ticket, and excluded from
everything a customer can read.

This is the MVP's boundary doing its job unchanged. No chat-specific filter exists, and none
should: a second filter is a second thing to forget.
"""

import pytest
from django.urls import reverse

from apps.chat.services import messaging
from apps.chat.services.redis_client import reset_for_tests
from apps.tickets.models import Message
from apps.tickets.services.visibility import public_messages_for, staff_messages_for

pytestmark = pytest.mark.django_db

NOTE = "Do not offer a refund, the policy changed on Sunday"


@pytest.fixture(autouse=True)
def clean():
    reset_for_tests()
    yield
    reset_for_tests()


@pytest.fixture
def conversation_with_a_note(conversation, agent, supervisor):
    messaging.visitor_message(conversation, "Can I have a refund?")
    messaging.whisper(conversation, supervisor, NOTE)
    messaging.agent_message(conversation, agent, "Let me check what we can do")
    return conversation


def test_staff_see_it_in_the_transcript(conversation_with_a_note):
    bodies = [m.body for m in staff_messages_for(conversation_with_a_note.ticket)]

    assert NOTE in bodies


def test_it_keeps_its_place_in_the_order(conversation_with_a_note):
    """A note read out of sequence is coaching detached from what prompted it."""
    bodies = [m.body for m in staff_messages_for(conversation_with_a_note.ticket)]

    assert bodies.index("Can I have a refund?") < bodies.index(NOTE)
    assert bodies.index(NOTE) < bodies.index("Let me check what we can do")


def test_the_customer_facing_transcript_excludes_it(conversation_with_a_note):
    bodies = [m.body for m in public_messages_for(conversation_with_a_note.ticket)]

    assert NOTE not in bodies
    assert bodies == ["Can I have a refund?", "Let me check what we can do"]


def test_the_agents_ticket_view_shows_it(agent_client, conversation_with_a_note):
    body = agent_client.get(
        reverse("tickets:detail", args=[conversation_with_a_note.ticket.reference])
    ).content.decode()

    assert NOTE in body


def test_an_emailed_reply_never_carries_it(agent_client, conversation_with_a_note):
    """The irreversible path. Once the mail has left there is nothing to recall."""
    from django.core import mail

    mail.outbox.clear()
    agent_client.post(
        reverse("tickets:reply", args=[conversation_with_a_note.ticket.reference]),
        {"body": "Here is what we can do about the refund."},
    )

    assert len(mail.outbox) == 1
    assert NOTE not in mail.outbox[0].body
    for content, _mime in getattr(mail.outbox[0], "alternatives", []):
        assert NOTE not in content


def test_attaching_the_conversation_carries_the_note_with_it(
    agent_client, conversation_with_a_note, department, branch, category, contact
):
    """The note moves with the transcript it belongs to. Leaving it on the retired placeholder
    would quietly sever coaching from the conversation it was about."""
    from apps.tickets.models import Ticket

    target = Ticket.objects.create(
        contact=contact,
        subject="Refund query raised last week",
        description="",
        category=category,
        origin_channel=Ticket.Channel.EMAIL,
        department=department,
        branch=branch,
    )

    agent_client.post(
        reverse("chat:attach", args=[conversation_with_a_note.pk]), {"ticket": target.pk}
    )

    assert target.messages.filter(body=NOTE, visibility=Message.Visibility.INTERNAL).exists()
    assert NOTE not in [m.body for m in public_messages_for(target)]
