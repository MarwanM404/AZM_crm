"""
Waiting, with a position that moves (T102, T108, FR-016).

The failure this guards against is the one every chat widget makes: a spinner that never
resolves. A visitor who is told "you are third" and then "you are second" is waiting; a
visitor watching an animation is being ignored with better graphics.

So the position is a fact the server pushes when it changes, not something the client polls
for and guesses at.
"""

import pytest
from django.urls import reverse

from apps.chat.models import Conversation
from apps.chat.services import lifecycle, presence, queue
from apps.chat.services.redis_client import reset_for_tests

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clean():
    reset_for_tests()
    yield
    reset_for_tests()


def start_chat(client, category, name="Visitor"):
    return client.post(
        reverse("chat:start"),
        {
            "full_name": name,
            "email": f"{name.lower()}@example.com",
            "subject": "Help please",
            "category": category.pk,
        },
    ).json()


def test_a_visitor_is_assigned_when_an_agent_is_free(client, agent, category, department, branch):
    presence.go_online(agent.pk, capacity=1)

    body = start_chat(client, category)

    assert body["assigned"] is True
    assert body["position"] is None


def test_a_visitor_queues_when_every_agent_is_at_capacity(
    client, agent, category, department, branch
):
    presence.go_online(agent.pk, capacity=1)
    start_chat(client, category, "First")

    second = start_chat(client, category, "Second")

    assert second["assigned"] is False
    assert second["position"] == 1


def test_the_position_reflects_how_many_are_ahead(client, agent, category, department, branch):
    presence.go_online(agent.pk, capacity=1)
    start_chat(client, category, "First")
    start_chat(client, category, "Second")

    third = start_chat(client, category, "Third")

    assert third["position"] == 2


def test_a_queued_conversation_is_waiting_not_active(client, agent, category, department, branch):
    presence.go_online(agent.pk, capacity=1)
    start_chat(client, category, "First")
    second = start_chat(client, category, "Second")

    conversation = Conversation.objects.get(pk=second["conversation"])
    assert conversation.state == Conversation.State.WAITING
    assert conversation.assigned_to_id is None


def test_the_queue_moves_when_a_conversation_ends(client, agent, category, department, branch):
    """The gap this phase closes. Freeing a slot without pulling the next visitor leaves
    somebody waiting behind an agent who is idle."""
    presence.go_online(agent.pk, capacity=1)
    first = start_chat(client, category, "First")
    second = start_chat(client, category, "Second")
    assert second["position"] == 1

    lifecycle.end(
        Conversation.objects.get(pk=first["conversation"]),
        reason=Conversation.EndReason.ENDED_BY_VISITOR,
    )

    waiting = Conversation.objects.get(pk=second["conversation"])
    assert waiting.state == Conversation.State.ACTIVE
    assert waiting.assigned_to_id == agent.pk


def test_the_positions_behind_move_up(client, agent, category, department, branch):
    presence.go_online(agent.pk, capacity=1)
    first = start_chat(client, category, "First")
    start_chat(client, category, "Second")
    third = start_chat(client, category, "Third")
    assert third["position"] == 2

    lifecycle.end(
        Conversation.objects.get(pk=first["conversation"]),
        reason=Conversation.EndReason.ENDED_BY_VISITOR,
    )

    assert queue.position(str(third["conversation"]), department.pk, branch.pk) == 1


def test_the_visitor_who_was_pulled_is_no_longer_in_the_queue(
    client, agent, category, department, branch
):
    """Left in the queue they would be handed to the next free agent as well, and two agents
    would arrive in one conversation."""
    presence.go_online(agent.pk, capacity=1)
    first = start_chat(client, category, "First")
    second = start_chat(client, category, "Second")

    lifecycle.end(
        Conversation.objects.get(pk=first["conversation"]),
        reason=Conversation.EndReason.ENDED_BY_VISITOR,
    )

    assert queue.position(str(second["conversation"]), department.pk, branch.pk) is None


def test_nothing_is_pulled_when_the_queue_is_empty(client, agent, category, department, branch):
    presence.go_online(agent.pk, capacity=1)
    first = start_chat(client, category, "Only")

    lifecycle.end(
        Conversation.objects.get(pk=first["conversation"]),
        reason=Conversation.EndReason.ENDED_BY_VISITOR,
    )

    assert queue.waiting_count(department.pk, branch.pk) == 0
    assert presence.capacity_remaining(agent.pk) == 1


def test_a_visitor_is_told_their_new_position(client, agent, category, department, branch):
    """A position that only the server knows is not a position the visitor is waiting on."""
    from apps.chat.services import groups

    presence.go_online(agent.pk, capacity=1)
    first = start_chat(client, category, "First")
    start_chat(client, category, "Second")
    third = start_chat(client, category, "Third")

    sent = []
    original = queue._publish
    queue._publish = lambda group, payload: sent.append((group, payload))
    try:
        lifecycle.end(
            Conversation.objects.get(pk=first["conversation"]),
            reason=Conversation.EndReason.ENDED_BY_VISITOR,
        )
    finally:
        queue._publish = original

    third_group = groups.public_group(third["conversation"])
    updates = [payload for group, payload in sent if group == third_group]
    assert updates and updates[-1]["position"] == 1
