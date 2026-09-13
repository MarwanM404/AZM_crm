"""
A visitor who closes the panel stops holding a place (T106, FR-019).

Two things go wrong if they do not. The people behind them wait for someone who left, and an
agent is eventually handed a conversation nobody is waiting on — they say hello to an empty
room, and the slot they are holding is real capacity taken from someone who is still there.
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


@pytest.fixture
def queued(client, agent, category, department, branch):
    presence.go_online(agent.pk, capacity=1)
    held = start_chat(client, category, "Holder")
    waiting = start_chat(client, category, "Leaver")
    return held, waiting


def test_leaving_removes_them_from_the_queue(client, queued, department, branch):
    _held, waiting = queued

    client.post(reverse("chat:leave_queue"), {"conversation": waiting["conversation"]})

    assert queue.position(str(waiting["conversation"]), department.pk, branch.pk) is None
    assert queue.waiting_count(department.pk, branch.pk) == 0


def test_no_agent_is_then_assigned_their_conversation(client, queued, agent, department, branch):
    """The failure this prevents: an agent greeting an empty room while holding a slot
    somebody who is still waiting could have used."""
    held, waiting = queued
    client.post(reverse("chat:leave_queue"), {"conversation": waiting["conversation"]})

    lifecycle.end(
        Conversation.objects.get(pk=held["conversation"]),
        reason=Conversation.EndReason.ENDED_BY_VISITOR,
    )

    gone = Conversation.objects.get(pk=waiting["conversation"])
    assert gone.assigned_to_id is None
    assert presence.capacity_remaining(agent.pk) == 1


def test_the_person_behind_moves_up(client, agent, category, department, branch):
    presence.go_online(agent.pk, capacity=1)
    start_chat(client, category, "Holder")
    leaver = start_chat(client, category, "Leaver")
    behind = start_chat(client, category, "Behind")
    assert behind["position"] == 2

    client.post(reverse("chat:leave_queue"), {"conversation": leaver["conversation"]})

    assert queue.position(str(behind["conversation"]), department.pk, branch.pk) == 1


def test_leaving_twice_is_harmless(client, queued, department, branch):
    """A closing browser can fire the same beacon more than once."""
    _held, waiting = queued

    client.post(reverse("chat:leave_queue"), {"conversation": waiting["conversation"]})
    response = client.post(reverse("chat:leave_queue"), {"conversation": waiting["conversation"]})

    assert response.status_code == 200
    assert queue.waiting_count(department.pk, branch.pk) == 0


def test_an_unknown_conversation_is_harmless(client, department, branch):
    response = client.post(reverse("chat:leave_queue"), {"conversation": "999999"})

    assert response.status_code == 200


def test_a_missing_conversation_id_is_harmless(client, department, branch):
    response = client.post(reverse("chat:leave_queue"), {})

    assert response.status_code == 200


def test_leaving_does_not_disturb_anyone_elses_place(client, agent, category, department, branch):
    """Removal by token, so it cannot take the wrong person out of the queue."""
    presence.go_online(agent.pk, capacity=1)
    start_chat(client, category, "Holder")
    first = start_chat(client, category, "First")
    second = start_chat(client, category, "Second")

    client.post(reverse("chat:leave_queue"), {"conversation": second["conversation"]})

    assert queue.position(str(first["conversation"]), department.pk, branch.pk) == 1
    assert queue.waiting_count(department.pk, branch.pk) == 1
