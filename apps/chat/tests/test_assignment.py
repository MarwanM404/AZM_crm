"""
Assignment (T014, T028).

The same race as taking a ticket in the MVP, with an extra wrinkle: capacity lives in Redis
and the assignment lives in PostgreSQL, so "claim a slot and attach the agent" spans two
stores. If the slot is claimed and the attach then fails, the agent leaks capacity and
gradually stops receiving conversations for no visible reason.
"""

import pytest

from apps.chat.models import Conversation
from apps.chat.services import assignment, presence
from apps.chat.services.redis_client import reset_for_tests


@pytest.fixture(autouse=True)
def clean():
    reset_for_tests()
    yield
    reset_for_tests()


@pytest.fixture
def waiting_conversation(db, department, branch, category, contact):
    from apps.tickets.models import Ticket

    ticket = Ticket.objects.create(
        contact=contact,
        subject="Chat",
        description="",
        category=category,
        origin_channel=Ticket.Channel.CHAT,
        department=department,
        branch=branch,
    )
    return Conversation.objects.create(
        ticket=ticket,
        contact=contact,
        visitor_token_hash="hash",
        department=department,
        branch=branch,
    )


@pytest.mark.django_db
def test_an_online_agent_with_room_is_assigned(waiting_conversation, agent):
    presence.go_online(agent.pk, capacity=1)

    assigned = assignment.assign(waiting_conversation, [agent.pk])

    assert assigned == agent.pk
    waiting_conversation.refresh_from_db()
    assert waiting_conversation.assigned_to_id == agent.pk
    assert waiting_conversation.state == Conversation.State.ACTIVE
    assert waiting_conversation.assigned_at is not None


@pytest.mark.django_db
def test_an_agent_at_capacity_is_not_assigned(waiting_conversation, agent):
    presence.go_online(agent.pk, capacity=1)
    presence.claim_slot(agent.pk)

    assert assignment.assign(waiting_conversation, [agent.pk]) is None
    waiting_conversation.refresh_from_db()
    assert waiting_conversation.assigned_to_id is None
    assert waiting_conversation.state == Conversation.State.WAITING


@pytest.mark.django_db
def test_an_offline_agent_is_not_assigned(waiting_conversation, agent):
    assert assignment.assign(waiting_conversation, [agent.pk]) is None


@pytest.mark.django_db
def test_assignment_consumes_exactly_one_slot(waiting_conversation, agent):
    presence.go_online(agent.pk, capacity=3)
    assignment.assign(waiting_conversation, [agent.pk])
    assert presence.capacity_remaining(agent.pk) == 2


@pytest.mark.django_db
def test_an_already_assigned_conversation_is_not_reassigned(
    waiting_conversation, agent, other_agent
):
    presence.go_online(agent.pk, capacity=3)
    presence.go_online(other_agent.pk, capacity=3)
    assignment.assign(waiting_conversation, [agent.pk])

    assert assignment.assign(waiting_conversation, [other_agent.pk]) is None
    waiting_conversation.refresh_from_db()
    assert waiting_conversation.assigned_to_id == agent.pk


@pytest.mark.django_db
def test_a_failed_attach_returns_the_slot(waiting_conversation, agent, monkeypatch):
    """The two-store wrinkle. If the slot is claimed and the database write then fails, the
    agent silently loses capacity forever and stops receiving conversations for no visible
    reason. The slot must come back."""
    presence.go_online(agent.pk, capacity=1)

    def boom(*args, **kwargs):
        raise RuntimeError("database went away")

    monkeypatch.setattr(Conversation, "save", boom)

    with pytest.raises(RuntimeError):
        assignment.assign(waiting_conversation, [agent.pk])

    assert presence.capacity_remaining(agent.pk) == 1


@pytest.mark.django_db
def test_releasing_a_conversation_frees_the_agent(waiting_conversation, agent):
    presence.go_online(agent.pk, capacity=1)
    assignment.assign(waiting_conversation, [agent.pk])

    assignment.release(waiting_conversation)

    assert presence.has_capacity(agent.pk) is True


@pytest.mark.django_db
def test_the_first_agent_with_room_is_chosen(waiting_conversation, agent, other_agent):
    presence.go_online(agent.pk, capacity=1)
    presence.claim_slot(agent.pk)
    presence.go_online(other_agent.pk, capacity=1)

    assert assignment.assign(waiting_conversation, [agent.pk, other_agent.pk]) == other_agent.pk
