"""
Longest waiting, first served (T103, FR-017).

Fairness in a queue is not a nicety: the visitor who has waited longest is the one closest to
giving up, and an unfair queue starves exactly the person it is most important not to lose.

The rule is enforced by the data structure — a sorted set scored by arrival time — so most of
what these tests check is that nothing *re-scores* an entry. Every bug in queue fairness looks
like a timestamp being refreshed by something that should not have touched it.
"""

import time

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


def start_chat(client, category, name):
    return client.post(
        reverse("chat:start"),
        {
            "full_name": name,
            "email": f"{name.lower()}@example.com",
            "subject": "Help",
            "category": category.pk,
        },
    ).json()


def test_the_longest_waiting_visitor_is_connected_first(
    client, agent, category, department, branch
):
    presence.go_online(agent.pk, capacity=1)
    held = start_chat(client, category, "Holder")
    first_waiting = start_chat(client, category, "Early")
    start_chat(client, category, "Late")

    lifecycle.end(
        Conversation.objects.get(pk=held["conversation"]),
        reason=Conversation.EndReason.ENDED_BY_VISITOR,
    )

    connected = Conversation.objects.get(pk=first_waiting["conversation"])
    assert connected.state == Conversation.State.ACTIVE


def test_joining_twice_does_not_improve_or_lose_a_place(department, branch):
    """A visitor with two browser tabs is one person waiting — and must not be re-scored to
    the back of the queue by the second tab either."""
    queue.join("10", department.pk, branch.pk)
    time.sleep(0.01)
    queue.join("20", department.pk, branch.pk)
    time.sleep(0.01)
    queue.join("10", department.pk, branch.pk)

    assert queue.position("10", department.pk, branch.pk) == 1
    assert queue.position("20", department.pk, branch.pk) == 2


def test_a_failed_assignment_leaves_every_place_untouched(
    client, agent, category, department, branch
):
    """When there is no free agent, the queue must be exactly as it was.

    This is why the assignment loop peeks and only removes after an agent is attached. The
    alternative — take, try, put back — needs a put-back that preserves the arrival score,
    because re-queuing by arrival-time-now sends the longest-waiting visitor to the back at
    the precise moment the system failed to serve them. Not removing them avoids the choice.
    """
    presence.go_online(agent.pk, capacity=1)
    start_chat(client, category, "Holder")
    first = start_chat(client, category, "First")
    second = start_chat(client, category, "Second")

    # No agent has capacity, so there is nothing to give anyone.
    connected = lifecycle.connect_next_waiting(department.pk, branch.pk)

    assert connected == []
    assert queue.position(str(first["conversation"]), department.pk, branch.pk) == 1
    assert queue.position(str(second["conversation"]), department.pk, branch.pk) == 2


def test_peeking_does_not_remove(department, branch):
    """Choosing is not taking. A visitor removed before they have an agent is a visitor who
    has silently left the queue if the assignment then fails."""
    queue.join("10", department.pk, branch.pk)

    queue.peek(department.pk, branch.pk)

    assert queue.position("10", department.pk, branch.pk) == 1
    assert queue.waiting_count(department.pk, branch.pk) == 1


def test_a_visitor_who_leaves_does_not_hold_up_the_one_behind(
    client, agent, category, department, branch
):
    """FR-019. Their place is released rather than skipped over on every future pull."""
    presence.go_online(agent.pk, capacity=1)
    held = start_chat(client, category, "Holder")
    leaving = start_chat(client, category, "Leaving")
    behind = start_chat(client, category, "Behind")

    client.post(reverse("chat:leave_queue"), {"conversation": leaving["conversation"]})
    lifecycle.end(
        Conversation.objects.get(pk=held["conversation"]),
        reason=Conversation.EndReason.ENDED_BY_VISITOR,
    )

    assert Conversation.objects.get(pk=behind["conversation"]).state == (Conversation.State.ACTIVE)


def test_a_conversation_that_ended_while_queued_is_skipped(
    client, agent, category, department, branch
):
    """A visitor whose conversation ended while they waited must not consume the slot their
    neighbour is waiting for."""
    presence.go_online(agent.pk, capacity=1)
    held = start_chat(client, category, "Holder")
    gone = start_chat(client, category, "Gone")
    behind = start_chat(client, category, "Behind")

    lifecycle.end(
        Conversation.objects.get(pk=gone["conversation"]),
        reason=Conversation.EndReason.VISITOR_DISCONNECTED,
    )
    lifecycle.end(
        Conversation.objects.get(pk=held["conversation"]),
        reason=Conversation.EndReason.ENDED_BY_VISITOR,
    )

    assert Conversation.objects.get(pk=behind["conversation"]).state == (Conversation.State.ACTIVE)
