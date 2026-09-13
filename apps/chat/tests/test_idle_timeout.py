"""
Warned before it closes, not after (T115, T120, FR-036).

The requirement is specifically about order. A conversation that closes and then says "this
was closed for inactivity" has told the customer something they can do nothing about; one that
says "this will close soon" gives someone who stepped away for coffee a chance to say they are
still there.

Idle is measured from `last_activity_at`, which deliberately excludes internal notes — a
supervisor writing about a customer who left is not the customer being present. That decision
lives in apps/chat/services/messaging.py and is asserted here, because this is the feature
that would silently break if it were ever reversed.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.chat.models import Conversation
from apps.chat.services import liveness, messaging
from apps.chat.services.redis_client import reset_for_tests
from apps.chat.tasks import sweep_idle_conversations

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


def idle_for(conversation, seconds):
    Conversation.objects.filter(pk=conversation.pk).update(
        last_activity_at=timezone.now() - timedelta(seconds=seconds)
    )
    conversation.refresh_from_db()


def test_a_busy_conversation_is_left_alone(live):
    result = sweep_idle_conversations()

    assert result == {"warned": 0, "closed": 0}


def test_it_is_warned_before_the_limit(live):
    idle_for(live, 500)  # past the 480s warning, short of the 600s limit

    result = sweep_idle_conversations()

    live.refresh_from_db()
    assert result["warned"] == 1
    assert result["closed"] == 0
    assert live.state == Conversation.State.ACTIVE
    assert live.idle_warned_at is not None


def test_the_warning_says_it_will_close_rather_than_that_it_did(live):
    from apps.chat.services import messaging as messaging_module

    idle_for(live, 500)
    sent = []
    original = messaging_module._broadcast
    messaging_module._broadcast = lambda group, payload: sent.append(payload)
    try:
        sweep_idle_conversations()
    finally:
        messaging_module._broadcast = original

    notices = [p.get("html", "") for p in sent]
    assert any("will close" in html for html in notices)


def test_both_parties_are_warned(live):
    """FR-036 says both. A warning only the agent sees is not a chance for the customer to
    say they are still there."""
    from apps.chat.services import groups
    from apps.chat.services import messaging as messaging_module

    idle_for(live, 500)
    sent = []
    original = messaging_module._broadcast
    messaging_module._broadcast = lambda group, payload: sent.append((group, payload))
    try:
        sweep_idle_conversations()
    finally:
        messaging_module._broadcast = original

    reached = {group for group, _payload in sent}
    assert groups.public_group(live.pk) in reached
    assert groups.staff_group(live.pk) in reached


def test_it_is_warned_only_once(live):
    idle_for(live, 500)
    sweep_idle_conversations()

    second = sweep_idle_conversations()

    assert second["warned"] == 0


def test_it_closes_at_the_limit(live):
    idle_for(live, 700)

    result = sweep_idle_conversations()

    live.refresh_from_db()
    assert result["closed"] == 1
    assert live.state == Conversation.State.ENDED
    assert live.end_reason == Conversation.EndReason.IDLE_TIMEOUT


def test_replying_after_the_warning_saves_it(live, agent):
    """The whole purpose of warning first."""
    idle_for(live, 500)
    sweep_idle_conversations()

    messaging.visitor_message(live, "Sorry, still here")
    result = sweep_idle_conversations()

    live.refresh_from_db()
    assert result["closed"] == 0
    assert live.state == Conversation.State.ACTIVE


def test_a_revived_conversation_is_warned_again_next_time(live, agent):
    """The mark has to clear, or a second silence would close with no warning at all — exactly
    what FR-036 forbids, and invisible unless someone tests the second time round."""
    idle_for(live, 500)
    sweep_idle_conversations()
    messaging.visitor_message(live, "Still here")
    live.refresh_from_db()
    assert live.idle_warned_at is None

    idle_for(live, 500)
    result = sweep_idle_conversations()

    assert result["warned"] == 1


def test_a_private_note_does_not_count_as_activity(live, supervisor):
    """A supervisor writing about a customer who left is not the customer being present. If
    this counted, a coached conversation would never time out and the agent's slot would be
    held all afternoon."""
    idle_for(live, 700)

    messaging.whisper(live, supervisor, "They have gone quiet — wrap this up")
    result = sweep_idle_conversations()

    live.refresh_from_db()
    assert result["closed"] == 1
    assert live.state == Conversation.State.ENDED


def test_the_transcript_survives_the_timeout(live, agent):
    messaging.visitor_message(live, "Said before the silence")
    idle_for(live, 700)

    sweep_idle_conversations()

    assert live.ticket.messages.filter(body="Said before the silence").exists()


def test_a_waiting_conversation_is_not_closed_for_being_idle(conversation):
    """Waiting in a queue is not being idle — they are doing exactly what they were asked to."""
    idle_for(conversation, 700)

    sweep_idle_conversations()

    conversation.refresh_from_db()
    assert conversation.state == Conversation.State.WAITING
