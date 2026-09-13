"""
The desk closes while people are still waiting (T105, T109, FR-042).

This is the cruellest version of the queue failure. The visitor did everything right — they
arrived while the desk was open, filled in the form, and took their place. Then the last agent
went home, and nothing told them. Without this they watch "you are 2nd in line" until they
give up, and the position is true: they are second in a queue that will never move again.

So the queue is drained the moment the last agent goes offline, and everyone in it is offered
the request form with what they already typed.
"""

import pytest
from django.urls import reverse

from apps.chat.models import Conversation
from apps.chat.services import presence, queue
from apps.chat.services.redis_client import reset_for_tests

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clean():
    reset_for_tests()
    yield
    reset_for_tests()


def start_chat(client, category, name="Waiting"):
    return client.post(
        reverse("chat:start"),
        {
            "full_name": name,
            "email": f"{name.lower()}@example.com",
            "subject": "Still waiting on my order",
            "category": category.pk,
        },
    ).json()


@pytest.fixture
def one_waiting(client, agent, category, department, branch):
    presence.go_online(agent.pk, capacity=1)
    held = start_chat(client, category, "Holder")
    waiting = start_chat(client, category, "Waiter")
    assert waiting["position"] == 1
    return held, waiting


def test_the_queue_is_emptied(one_waiting, agent, department, branch):
    from apps.chat.services import lifecycle

    presence.go_offline(agent.pk)
    lifecycle.desk_closed_if_empty(department.pk, branch.pk)

    assert queue.waiting_count(department.pk, branch.pk) == 0


def test_the_waiting_visitor_is_told_the_desk_closed(one_waiting, agent, department, branch):
    from apps.chat.services import groups, lifecycle

    _held, waiting = one_waiting
    sent = []
    original = queue._publish
    queue._publish = lambda group, payload: sent.append((group, payload))
    try:
        presence.go_offline(agent.pk)
        lifecycle.desk_closed_if_empty(department.pk, branch.pk)
    finally:
        queue._publish = original

    their_group = groups.public_group(waiting["conversation"])
    closures = [p for g, p in sent if g == their_group and p["type"] == "chat.desk_closed"]
    assert closures


def test_they_are_given_the_request_form_and_their_own_words(
    one_waiting, agent, department, branch
):
    from apps.chat.services import groups, lifecycle

    _held, waiting = one_waiting
    sent = []
    original = queue._publish
    queue._publish = lambda group, payload: sent.append((group, payload))
    try:
        presence.go_offline(agent.pk)
        lifecycle.desk_closed_if_empty(department.pk, branch.pk)
    finally:
        queue._publish = original

    their_group = groups.public_group(waiting["conversation"])
    closure = [p for g, p in sent if g == their_group][0]

    assert closure["fallback"] == reverse("intake:form")
    assert closure["carry"]["full_name"] == "Waiter"
    assert closure["carry"]["email"] == "waiter@example.com"
    assert closure["carry"]["subject"] == "Still waiting on my order"


def test_their_conversation_is_ended_rather_than_left_open(one_waiting, agent, department, branch):
    """A WAITING conversation nobody will ever take is a ticket that sits in the queue looking
    like work. It ends, with a reason that says what happened."""
    from apps.chat.services import lifecycle

    _held, waiting = one_waiting

    presence.go_offline(agent.pk)
    lifecycle.desk_closed_if_empty(department.pk, branch.pk)

    conversation = Conversation.objects.get(pk=waiting["conversation"])
    assert conversation.state == Conversation.State.ENDED
    assert conversation.end_reason == Conversation.EndReason.DESK_CLOSED


def test_the_transcript_survives(one_waiting, agent, department, branch):
    """They typed a subject. That became a ticket at the moment they started (FR-040), and it
    is still there for someone to answer tomorrow."""
    from apps.chat.services import lifecycle

    _held, waiting = one_waiting

    presence.go_offline(agent.pk)
    lifecycle.desk_closed_if_empty(department.pk, branch.pk)

    conversation = Conversation.objects.get(pk=waiting["conversation"])
    assert conversation.ticket is not None
    assert conversation.ticket.subject == "Still waiting on my order"


def test_nothing_happens_while_another_agent_is_still_online(
    one_waiting, agent, other_agent, department, branch
):
    """One of two agents leaving is not the desk closing. The queue keeps moving."""
    from apps.chat.services import lifecycle

    _held, waiting = one_waiting
    presence.go_online(other_agent.pk, capacity=1)

    presence.go_offline(agent.pk)
    lifecycle.desk_closed_if_empty(department.pk, branch.pk)

    conversation = Conversation.objects.get(pk=waiting["conversation"])
    assert conversation.state != Conversation.State.ENDED


def test_a_lapsed_heartbeat_strands_them_and_the_sweep_rescues_them(
    one_waiting, agent, department, branch
):
    """How this actually happens.

    The graceful path barely strands anyone: ending a conversation pulls the next visitor in
    immediately, and FR-014 refuses to let an agent go offline while holding anything. What
    strands people is the laptop that slept — the presence key stops being refreshed and
    expires, and no event fires at all. No event means no handler, which is why there is a
    sweep (apps/chat/tasks.py).
    """
    from apps.chat.services.redis_client import get_client
    from apps.chat.tasks import close_deserted_desks

    _held, waiting = one_waiting
    get_client().force_expire(f"chat:presence:{agent.pk}")

    moved = close_deserted_desks()

    assert moved == 1
    assert queue.waiting_count(department.pk, branch.pk) == 0
    assert Conversation.objects.get(pk=waiting["conversation"]).end_reason == (
        Conversation.EndReason.DESK_CLOSED
    )


def test_the_sweep_leaves_a_staffed_queue_alone(one_waiting, agent, department, branch):
    """It runs every minute against every department. Evicting a queue that is merely busy
    would be far worse than the problem it was written to solve."""
    from apps.chat.tasks import close_deserted_desks

    _held, waiting = one_waiting

    moved = close_deserted_desks()

    assert moved == 0
    assert queue.waiting_count(department.pk, branch.pk) == 1
    assert Conversation.objects.get(pk=waiting["conversation"]).state == (
        Conversation.State.WAITING
    )


def test_the_sweep_does_nothing_when_nobody_is_waiting(agent, department, branch):
    from apps.chat.tasks import close_deserted_desks

    assert close_deserted_desks() == 0


def test_going_offline_deliberately_also_checks(agent, department, branch, monkeypatch):
    """The rare path, but the one an agent can observe. Asserted on the call rather than on a
    contrived queue state, because arranging a real stranding through the graceful path takes
    a scenario that does not occur."""
    from apps.chat.services import lifecycle

    called = []
    monkeypatch.setattr(lifecycle, "desk_closed_if_empty", lambda d, b: called.append((d, b)) or [])

    import asyncio

    from channels.testing import WebsocketCommunicator

    from apps.chat.consumers.agent import AgentConsumer

    presence.go_online(agent.pk, capacity=1)

    async def run():
        communicator = WebsocketCommunicator(AgentConsumer.as_asgi(), "/ws/chat/agent/")
        communicator.scope["user"] = agent
        await communicator.connect()
        await communicator.send_json_to({"type": "offline"})
        await communicator.receive_from(timeout=2)
        await communicator.disconnect()

    asyncio.run(run())

    assert called == [(department.pk, branch.pk)]
