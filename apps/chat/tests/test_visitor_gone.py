"""
The customer did not come back (T112, FR-033).

Two things are needed and only one of them is obvious. The conversation ends and the
transcript is kept — which takes no work at all, because the transcript was never anywhere
else (apps/chat/services/transcript.py). The part that matters is telling the agent, who is
otherwise left typing to somebody who left ten minutes ago and wondering why they went quiet.
"""

import pytest

from apps.chat.models import Conversation
from apps.chat.services import liveness, messaging, presence
from apps.chat.services.redis_client import get_client, reset_for_tests
from apps.chat.tasks import sweep_interrupted_conversations

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


def visitor_drops(conversation):
    get_client().force_expire(f"chat:live:{conversation.pk}:visitor")


def test_a_visitor_still_present_is_left_alone(live):
    """The sweep runs every fifteen seconds against every active conversation. Ending one
    that is merely quiet would be far worse than the problem it solves."""
    result = sweep_interrupted_conversations()

    live.refresh_from_db()
    assert result == {"ended": 0, "requeued": 0}
    assert live.state == Conversation.State.ACTIVE


def test_a_visitor_who_does_not_return_ends_the_conversation(live):
    visitor_drops(live)

    sweep_interrupted_conversations()

    live.refresh_from_db()
    assert live.state == Conversation.State.ENDED
    assert live.end_reason == Conversation.EndReason.VISITOR_DISCONNECTED


def test_the_transcript_is_kept(live, agent):
    messaging.visitor_message(live, "My order is late")
    messaging.agent_message(live, agent, "Let me check")
    visitor_drops(live)

    sweep_interrupted_conversations()

    bodies = list(live.ticket.messages.values_list("body", flat=True))
    assert "My order is late" in bodies
    assert "Let me check" in bodies


def test_the_agent_is_told_why(live, agent):
    """Otherwise they are left waiting on someone who is not there."""
    from apps.chat.services import groups
    from apps.chat.services import messaging as messaging_module

    visitor_drops(live)
    sent = []
    original = messaging_module._broadcast
    messaging_module._broadcast = lambda group, payload: sent.append((group, payload))
    try:
        sweep_interrupted_conversations()
    finally:
        messaging_module._broadcast = original

    staff = groups.staff_group(live.pk)
    notices = [p["html"] for g, p in sent if g == staff and "html" in p]
    assert any("disconnected" in html for html in notices)


def test_the_customer_is_not_told_they_disconnected(live, agent):
    """They know. The notice exists for the agent, and sending it to a socket that is gone is
    at best pointless — but it would also be there waiting if they reconnected, telling a
    present customer that they left."""
    from apps.chat.services import groups
    from apps.chat.services import messaging as messaging_module

    visitor_drops(live)
    sent = []
    original = messaging_module._broadcast
    messaging_module._broadcast = lambda group, payload: sent.append((group, payload))
    try:
        sweep_interrupted_conversations()
    finally:
        messaging_module._broadcast = original

    public = groups.public_group(live.pk)
    public_notices = [p.get("html", "") for g, p in sent if g == public]
    assert not any("disconnected" in html for html in public_notices)


def test_the_agents_slot_is_released(live, agent):
    """The real cost of getting this wrong: an agent holding capacity for a conversation that
    ended, and a queue behind them that does not move."""
    before = presence.capacity_remaining(agent.pk)
    visitor_drops(live)

    sweep_interrupted_conversations()

    assert presence.capacity_remaining(agent.pk) == before + 1


def test_a_conversation_swept_once_is_not_swept_again(live):
    visitor_drops(live)
    sweep_interrupted_conversations()

    second = sweep_interrupted_conversations()

    assert second == {"ended": 0, "requeued": 0}


def test_a_waiting_conversation_is_not_swept(conversation):
    """Nobody has been assigned yet, so there is no agent being left in the dark and nothing
    to release. The queue's own rules cover these."""
    get_client().force_expire(f"chat:live:{conversation.pk}:visitor")

    sweep_interrupted_conversations()

    conversation.refresh_from_db()
    assert conversation.state == Conversation.State.WAITING
