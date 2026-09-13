"""
An account switched off mid-conversation (T116, MVP FR-026).

Deactivation already ends web sessions on the next request (apps/accounts/models.py). A
WebSocket is the case that rule does not cover on its own: it was authorized once, at the
handshake, and then stays open for as long as the network holds. Nothing re-checks it, so a
dismissed agent keeps reading a live customer conversation until they close the tab.

So deactivation has to reach the sockets, and it has to hand the conversations on — otherwise
the customer is left talking to somebody who no longer works here.
"""

import pytest

from apps.chat.models import Conversation
from apps.chat.services import liveness, messaging, presence, queue
from apps.chat.services.redis_client import reset_for_tests

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clean():
    reset_for_tests()
    yield
    reset_for_tests()


@pytest.fixture
def live(assigned_conversation, agent):
    liveness.seen(assigned_conversation.pk, liveness.VISITOR)
    liveness.seen(assigned_conversation.pk, liveness.AGENT)
    return assigned_conversation


def deactivate(user):
    user.is_active = False
    user.save(update_fields=["is_active"])


def test_their_conversation_returns_to_the_queue(live, agent, department, branch):
    deactivate(agent)

    live.refresh_from_db()
    assert live.state == Conversation.State.WAITING
    assert live.assigned_to_id is None


def test_the_customer_keeps_their_history(live, agent):
    messaging.visitor_message(live, "I have explained this twice already")

    deactivate(agent)

    assert live.ticket.messages.filter(body="I have explained this twice already").exists()


def test_the_customer_is_told_they_are_being_reconnected(live, agent):
    from apps.chat.services import groups
    from apps.chat.services import messaging as messaging_module

    sent = []
    original = messaging_module._broadcast
    messaging_module._broadcast = lambda group, payload: sent.append((group, payload))
    try:
        deactivate(agent)
    finally:
        messaging_module._broadcast = original

    public = groups.public_group(live.pk)
    notices = [p.get("html", "") for g, p in sent if g == public]
    assert any("Reconnecting" in html for html in notices)


def test_they_are_taken_offline(live, agent):
    """Otherwise they stay a candidate and the queue hands them the next visitor."""
    assert presence.is_online(agent.pk) is True

    deactivate(agent)

    assert presence.is_online(agent.pk) is False


def test_their_sockets_are_told_to_close(live, agent):
    """The gap a session check does not cover: a socket authorized at the handshake stays open
    until something closes it."""
    from apps.chat.services import lifecycle

    sent = []
    original = lifecycle._publish_to_agent
    lifecycle._publish_to_agent = lambda group, payload: sent.append((group, payload))
    try:
        deactivate(agent)
    finally:
        lifecycle._publish_to_agent = original

    assert any(payload.get("type") == "chat.disconnect" for _group, payload in sent)


def test_another_agent_picks_it_up(live, agent, other_agent):
    presence.go_online(other_agent.pk, capacity=1)

    deactivate(agent)

    live.refresh_from_db()
    assert live.state == Conversation.State.ACTIVE
    assert live.assigned_to_id == other_agent.pk


def test_it_waits_when_nobody_else_is_free(live, agent, department, branch):
    deactivate(agent)

    assert queue.position(str(live.pk), department.pk, branch.pk) == 1


def test_reactivating_does_not_hand_the_conversation_back(live, agent):
    """Coming back is not the same as never having gone. The conversation has moved on, and
    quietly reversing a deactivation would undo an administrative decision."""
    deactivate(agent)
    agent.is_active = True
    agent.save(update_fields=["is_active"])

    live.refresh_from_db()
    assert live.assigned_to_id is None


def test_an_ordinary_save_changes_nothing(live, agent):
    """Deactivation is the trigger, not saving the row. An agent renamed mid-conversation
    must not lose it."""
    agent.full_name = "Agent One Renamed"
    agent.save(update_fields=["full_name"])

    live.refresh_from_db()
    assert live.state == Conversation.State.ACTIVE
    assert live.assigned_to_id == agent.pk


def test_deactivating_an_agent_with_no_conversations_is_harmless(agent):
    deactivate(agent)

    assert presence.is_online(agent.pk) is False
