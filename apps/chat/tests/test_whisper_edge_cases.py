"""
Whispers at the awkward moments (T095, T099).

Two of them, and both are ordinary rather than exotic: the agent's connection drops for a few
seconds while a supervisor is typing, and a supervisor presses send as the conversation ends.
Neither should lose the note, and neither should deliver it to the wrong person.
"""

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator

from apps.chat.consumers.agent import AgentConsumer
from apps.chat.models import Conversation
from apps.chat.services import messaging, pending, presence
from apps.chat.services.redis_client import reset_for_tests
from apps.tickets.models import Message

pytestmark = pytest.mark.django_db(transaction=True)

NOTE = "Walk back the refund promise gently"


@pytest.fixture(autouse=True)
def clean():
    reset_for_tests()
    yield
    reset_for_tests()


async def open_agent(user):
    communicator = WebsocketCommunicator(AgentConsumer.as_asgi(), "/ws/chat/agent/")
    communicator.scope["user"] = user
    await communicator.connect()
    return communicator


# --- the agent was not listening ---


async def test_a_whisper_to_a_disconnected_agent_is_still_recorded(
    assigned_conversation, supervisor
):
    """Delivery and the record are separate concerns. The note is on the ticket whether or not
    anybody was listening."""
    await database_sync_to_async(messaging.whisper)(assigned_conversation, supervisor, NOTE)

    exists = await database_sync_to_async(
        lambda: Message.objects.filter(body=NOTE, visibility=Message.Visibility.INTERNAL).exists()
    )()
    assert exists


async def test_it_is_held_for_the_agent_who_is_away(assigned_conversation, supervisor, agent):
    await database_sync_to_async(messaging.whisper)(assigned_conversation, supervisor, NOTE)

    waiting = await database_sync_to_async(pending.waiting)(assigned_conversation.pk, agent.pk)
    assert waiting == 1


async def test_it_is_replayed_when_that_agent_reconnects(assigned_conversation, supervisor, agent):
    await database_sync_to_async(messaging.whisper)(assigned_conversation, supervisor, NOTE)

    agent_socket = await open_agent(agent)
    frame = await agent_socket.receive_from(timeout=2)

    assert NOTE in frame
    await agent_socket.disconnect()


async def test_it_is_replayed_only_once(assigned_conversation, supervisor, agent):
    """A bad connection flickers. A note repeated at every flicker gives the agent no way to
    tell one correction from four."""
    await database_sync_to_async(messaging.whisper)(assigned_conversation, supervisor, NOTE)

    first = await open_agent(agent)
    await first.receive_from(timeout=2)
    await first.disconnect()

    second = await open_agent(agent)
    assert await second.receive_nothing(timeout=0.5) is True
    await second.disconnect()


async def test_it_is_not_held_when_the_agent_is_listening(assigned_conversation, supervisor, agent):
    """Held *and* broadcast would deliver it twice: once now, once on the next reconnect."""
    agent_socket = await open_agent(agent)

    await database_sync_to_async(messaging.whisper)(assigned_conversation, supervisor, NOTE)
    assert NOTE in await agent_socket.receive_from(timeout=2)

    waiting = await database_sync_to_async(pending.waiting)(assigned_conversation.pk, agent.pk)
    assert waiting == 0
    await agent_socket.disconnect()


async def test_it_is_not_given_to_whoever_takes_the_conversation_over(
    assigned_conversation, supervisor, agent, other_agent
):
    """The note is coaching aimed at one person about a commitment *they* made. Replaying it
    to a stranger hands them a correction for something they never did."""
    await database_sync_to_async(messaging.whisper)(assigned_conversation, supervisor, NOTE)

    @database_sync_to_async
    def reassign():
        assigned_conversation.assigned_to = other_agent
        assigned_conversation.save(update_fields=["assigned_to"])

    await reassign()

    replacement = await open_agent(other_agent)
    assert await replacement.receive_nothing(timeout=0.5) is True
    await replacement.disconnect()


async def test_it_still_reaches_the_agent_it_was_written_for(
    assigned_conversation, supervisor, agent, other_agent
):
    """The other half of the same rule: keyed by agent, so the intended reader still gets it."""
    await database_sync_to_async(messaging.whisper)(assigned_conversation, supervisor, NOTE)

    intended = await open_agent(agent)
    assert NOTE in await intended.receive_from(timeout=2)
    await intended.disconnect()


async def test_a_held_note_expires_with_the_grace_period(assigned_conversation, supervisor, agent):
    """Replayed twenty minutes later it lands in a conversation that has moved on."""
    from apps.chat.services.redis_client import get_client

    await database_sync_to_async(messaging.whisper)(assigned_conversation, supervisor, NOTE)

    @database_sync_to_async
    def elapse():
        get_client().force_expire(f"chat:pending:{assigned_conversation.pk}:{agent.pk}")

    await elapse()

    agent_socket = await open_agent(agent)
    assert await agent_socket.receive_nothing(timeout=0.5) is True
    await agent_socket.disconnect()


# --- the conversation was ending ---


async def test_a_whisper_as_the_conversation_ends_is_still_recorded(
    assigned_conversation, supervisor, agent
):
    """The supervisor pressed send before the agent clicked end. The note is part of what
    happened, and the ticket outlives the conversation."""

    @database_sync_to_async
    def end_it():
        from apps.chat.services import lifecycle

        lifecycle.end(
            assigned_conversation,
            reason=Conversation.EndReason.ENDED_BY_AGENT,
            ended_by=agent,
        )

    await end_it()
    await database_sync_to_async(messaging.whisper)(assigned_conversation, supervisor, NOTE)

    exists = await database_sync_to_async(lambda: Message.objects.filter(body=NOTE).exists())()
    assert exists


async def test_a_whisper_after_the_end_never_reaches_the_customer(
    assigned_conversation, supervisor, agent
):
    """The conversation ending does not relax the boundary."""
    from apps.chat.services import groups

    sent = []
    original = messaging._broadcast
    messaging._broadcast = lambda group, payload: sent.append(group)
    try:
        await database_sync_to_async(messaging.whisper)(assigned_conversation, supervisor, NOTE)
    finally:
        messaging._broadcast = original

    assert groups.public_group(assigned_conversation.pk) not in sent


async def test_presence_says_the_socket_is_gone_after_disconnect(assigned_conversation, agent):
    """The signal the holding decision rests on. If this stayed true after a disconnect,
    whispers would be dropped rather than held."""
    agent_socket = await open_agent(agent)
    assert await database_sync_to_async(presence.has_socket)(agent.pk) is True

    await agent_socket.disconnect()

    assert await database_sync_to_async(presence.has_socket)(agent.pk) is False
