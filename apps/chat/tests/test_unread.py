"""
Unread counts (T053, T058).

Kept in Redis rather than in the socket, because an agent who reloads the console must not
lose track of which conversations need them — but not in PostgreSQL either, because an unread
count is a fact about a session, not about the conversation. It is the same shape as presence:
ephemeral, per agent, and worthless once they have gone.
"""

import pytest

from apps.chat.services import unread
from apps.chat.services.redis_client import reset_for_tests


@pytest.fixture(autouse=True)
def clean():
    reset_for_tests()
    yield
    reset_for_tests()


@pytest.mark.django_db
def test_a_conversation_starts_with_nothing_unread(agent, conversation):
    assert unread.count(agent.pk, conversation.pk) == 0
    assert unread.all_for(agent.pk) == {}


@pytest.mark.django_db
def test_a_message_marks_the_conversation_unread(agent, conversation):
    unread.mark(agent.pk, conversation.pk)
    assert unread.count(agent.pk, conversation.pk) == 1


@pytest.mark.django_db
def test_unread_accumulates(agent, conversation):
    for _ in range(3):
        unread.mark(agent.pk, conversation.pk)
    assert unread.count(agent.pk, conversation.pk) == 3


@pytest.mark.django_db
def test_opening_a_conversation_clears_it(agent, conversation):
    unread.mark(agent.pk, conversation.pk)
    unread.mark(agent.pk, conversation.pk)
    unread.clear(agent.pk, conversation.pk)
    assert unread.count(agent.pk, conversation.pk) == 0


@pytest.mark.django_db
def test_counts_are_per_conversation_not_per_agent(
    agent, conversation, department, branch, category, contact
):
    """An agent holding three conversations needs to know *which* one is waiting on them —
    a single total tells them something is happening and nothing about where."""
    from apps.chat.models import Conversation
    from apps.tickets.models import Ticket

    ticket = Ticket.objects.create(
        contact=contact,
        subject="Second",
        description="",
        category=category,
        origin_channel=Ticket.Channel.CHAT,
        department=department,
        branch=branch,
    )
    other = Conversation.objects.create(
        ticket=ticket,
        contact=contact,
        visitor_token_hash="y" * 64,
        department=department,
        branch=branch,
    )

    unread.mark(agent.pk, conversation.pk)
    unread.mark(agent.pk, other.pk)
    unread.mark(agent.pk, other.pk)

    assert unread.all_for(agent.pk) == {conversation.pk: 1, other.pk: 2}


@pytest.mark.django_db
def test_counts_are_per_agent(agent, other_agent, conversation):
    unread.mark(agent.pk, conversation.pk)
    assert unread.count(other_agent.pk, conversation.pk) == 0


@pytest.mark.django_db
def test_ending_a_conversation_forgets_its_count(agent, conversation):
    """An ended conversation that still shows unread is a badge nobody can clear."""
    unread.mark(agent.pk, conversation.pk)
    unread.forget(conversation.pk, [agent.pk])
    assert unread.all_for(agent.pk) == {}
