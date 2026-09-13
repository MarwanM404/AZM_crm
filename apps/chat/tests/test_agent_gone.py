"""
The agent did not come back (T113, T118, FR-034).

The conversation returns to the queue rather than ending, and it is the *same* conversation —
same row, same ticket, same transcript. Being asked to explain the problem again from the
start is the part of a handover customers actually mind, and it is the part that is entirely
avoidable.
"""

import pytest

from apps.chat.models import Conversation
from apps.chat.services import liveness, messaging, presence, queue
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


def agent_drops(conversation):
    get_client().force_expire(f"chat:live:{conversation.pk}:agent")


def test_the_conversation_returns_to_the_queue(live, agent):
    agent_drops(live)

    result = sweep_interrupted_conversations()

    live.refresh_from_db()
    assert result["requeued"] == 1
    assert live.state == Conversation.State.WAITING
    assert live.assigned_to_id is None


def test_it_keeps_its_history(live, agent):
    messaging.visitor_message(live, "My order is late and I have the reference here")
    agent_drops(live)

    sweep_interrupted_conversations()

    bodies = list(live.ticket.messages.values_list("body", flat=True))
    assert "My order is late and I have the reference here" in bodies


def test_it_keeps_its_ticket(live, agent):
    """A new ticket would split one problem across two records, and the customer would be
    given a reference that has half their conversation in it."""
    ticket_id = live.ticket_id
    agent_drops(live)

    sweep_interrupted_conversations()

    live.refresh_from_db()
    assert live.ticket_id == ticket_id


def test_the_customer_is_told_they_are_being_reconnected(live, agent):
    """Silence here reads as being ignored. It is the difference between a system that had a
    problem and a company that stopped replying."""
    from apps.chat.services import groups
    from apps.chat.services import messaging as messaging_module

    agent_drops(live)
    sent = []
    original = messaging_module._broadcast
    messaging_module._broadcast = lambda group, payload: sent.append((group, payload))
    try:
        sweep_interrupted_conversations()
    finally:
        messaging_module._broadcast = original

    public = groups.public_group(live.pk)
    notices = [p.get("html", "") for g, p in sent if g == public]
    assert any("Reconnecting" in html for html in notices)


def test_the_lost_agents_slot_is_released(live, agent):
    before = presence.capacity_remaining(agent.pk)
    agent_drops(live)

    sweep_interrupted_conversations()

    assert presence.capacity_remaining(agent.pk) == before + 1


def test_another_free_agent_picks_it_up_immediately(live, agent, other_agent):
    """Requeued and then connected in the same breath, when somebody is free. Leaving it in
    the queue until the next event would make a lost agent look like a long wait."""
    presence.go_online(other_agent.pk, capacity=1)
    agent_drops(live)

    sweep_interrupted_conversations()

    live.refresh_from_db()
    assert live.state == Conversation.State.ACTIVE
    assert live.assigned_to_id == other_agent.pk


def test_it_waits_in_the_queue_when_nobody_is_free(live, agent, department, branch):
    agent_drops(live)

    sweep_interrupted_conversations()

    assert queue.position(str(live.pk), department.pk, branch.pk) == 1


def test_a_note_left_for_the_lost_agent_is_not_handed_on(live, agent, supervisor, other_agent):
    """A whisper is coaching aimed at one person about how *they* were handling this. The
    agent who takes over never made the commitment it corrects."""
    from apps.chat.services import pending

    messaging.whisper(live, supervisor, "Walk back the refund you promised")
    assert pending.waiting(live.pk, agent.pk) == 1

    agent_drops(live)
    sweep_interrupted_conversations()

    assert pending.waiting(live.pk, agent.pk) == 0
    assert pending.waiting(live.pk, other_agent.pk) == 0


def test_an_agent_still_present_is_left_alone(live):
    result = sweep_interrupted_conversations()

    live.refresh_from_db()
    assert result["requeued"] == 0
    assert live.state == Conversation.State.ACTIVE


def test_a_gone_visitor_takes_precedence_over_a_gone_agent(live, agent):
    """Both dropped — most likely the server restarted. Ending is right: requeueing would put
    a conversation nobody is in front of into the queue, and the next free agent would greet
    an empty room."""
    get_client().force_expire(f"chat:live:{live.pk}:visitor")
    get_client().force_expire(f"chat:live:{live.pk}:agent")

    sweep_interrupted_conversations()

    live.refresh_from_db()
    assert live.state == Conversation.State.ENDED
    assert live.end_reason == Conversation.EndReason.VISITOR_DISCONNECTED


# --- the real path, not the fixture ---


def test_a_freshly_assigned_conversation_is_not_swept(client, agent, category, department, branch):
    """Every test above seeds liveness by hand, which is exactly how a sweep this destructive
    gets shipped broken: the fixture supplies the state the real code forgot to write.

    Here the conversation is created the way a visitor creates one, and the only question is
    whether ordinary assignment leaves it in a state the sweep will leave alone.
    """
    from django.urls import reverse

    presence.go_online(agent.pk, capacity=1)
    body = client.post(
        reverse("chat:start"),
        {
            "full_name": "Sara",
            "email": "sara@example.com",
            "subject": "Where is my order",
            "category": category.pk,
        },
    ).json()
    assert body["assigned"] is True

    result = sweep_interrupted_conversations()

    live = Conversation.objects.get(pk=body["conversation"])
    assert result == {"ended": 0, "requeued": 0}
    assert live.state == Conversation.State.ACTIVE
    assert live.assigned_to_id == agent.pk
