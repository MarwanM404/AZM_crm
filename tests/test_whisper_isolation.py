"""
The single most damaging failure in this product, tested from both ends (T089).

A private staff remark delivered into a customer's chat window, in real time, is
unrecallable. There is no retraction, no edit, no "unsend" — the customer has read it.

The assertion here is deliberately absolute: with a whisper in flight, the visitor's socket
must receive **nothing at all**. Not "nothing internal", not "no message with that body" —
nothing. Checking that what arrived was not the whisper would pass just as happily if the
whisper arrived mangled, truncated, or wrapped in a notification that something happened.

This test lives in tests/ rather than apps/chat/tests/ because it is an invariant about the
system, not about the chat app: the guarantee is the *absence of a route*, and it spans the
visitor consumer, the group naming, and the messaging service together.
"""

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator

from apps.chat.consumers.agent import AgentConsumer
from apps.chat.consumers.supervisor import SupervisorConsumer
from apps.chat.consumers.visitor import VisitorConsumer
from apps.chat.services import tokens
from apps.chat.services.redis_client import reset_for_tests

pytestmark = pytest.mark.django_db(transaction=True)

WHISPER = "Do not promise a refund, the policy changed on Sunday"


@pytest.fixture(autouse=True)
def clean():
    reset_for_tests()
    yield
    reset_for_tests()


async def open_visitor(conversation):
    token = await database_sync_to_async(tokens.issue)(conversation.pk)
    hashed = await database_sync_to_async(tokens.fingerprint)(token)

    @database_sync_to_async
    def store():
        conversation.visitor_token_hash = hashed
        conversation.save(update_fields=["visitor_token_hash"])

    await store()
    communicator = WebsocketCommunicator(
        VisitorConsumer.as_asgi(), f"/ws/chat/visitor/?token={token}"
    )
    await communicator.connect()
    await communicator.receive_from(timeout=2)  # connect-time `state`
    return communicator


async def open_agent(user):
    communicator = WebsocketCommunicator(AgentConsumer.as_asgi(), "/ws/chat/agent/")
    communicator.scope["user"] = user
    await communicator.connect()
    return communicator


async def open_supervisor(user, conversation_id):
    communicator = WebsocketCommunicator(
        SupervisorConsumer.as_asgi(), f"/ws/chat/supervise/?conversation={conversation_id}"
    )
    communicator.scope["user"] = user
    await communicator.connect()
    await communicator.receive_from(timeout=2)  # its own arrival notice
    return communicator


async def test_a_whisper_reaches_the_agent_and_the_visitor_receives_nothing_at_all(
    assigned_conversation, agent, supervisor
):
    visitor = await open_visitor(assigned_conversation)
    agent_socket = await open_agent(agent)
    observer = await open_supervisor(supervisor, assigned_conversation.pk)
    await agent_socket.receive_from(timeout=2)  # the observation notice

    await observer.send_json_to({"type": "whisper", "text": WHISPER})

    assert WHISPER in await agent_socket.receive_from(timeout=2)
    assert await visitor.receive_nothing(timeout=0.8) is True

    await observer.disconnect()
    await agent_socket.disconnect()
    await visitor.disconnect()


async def test_the_visitor_receives_nothing_even_across_several_whispers(
    assigned_conversation, agent, supervisor
):
    """One silent whisper could be a timing accident. Several cannot."""
    visitor = await open_visitor(assigned_conversation)
    observer = await open_supervisor(supervisor, assigned_conversation.pk)

    for index in range(3):
        await observer.send_json_to({"type": "whisper", "text": f"{WHISPER} {index}"})

    assert await visitor.receive_nothing(timeout=1.0) is True

    await observer.disconnect()
    await visitor.disconnect()


async def test_the_visitor_socket_is_demonstrably_alive(assigned_conversation, agent, supervisor):
    """The silence above must be specific to whispers. A visitor socket that was simply
    broken would satisfy every assertion in this file and prove nothing."""
    from apps.chat.services import messaging

    visitor = await open_visitor(assigned_conversation)
    observer = await open_supervisor(supervisor, assigned_conversation.pk)

    await observer.send_json_to({"type": "whisper", "text": WHISPER})
    assert await visitor.receive_nothing(timeout=0.8) is True

    await database_sync_to_async(messaging.agent_message)(
        assigned_conversation, agent, "A public reply the customer must see"
    )
    assert "A public reply" in await visitor.receive_from(timeout=2)

    await observer.disconnect()
    await visitor.disconnect()


async def test_a_whisper_sent_with_no_agent_connected_still_never_reaches_the_visitor(
    assigned_conversation, supervisor
):
    """The dangerous moment is the one where delivery to staff fails. A whisper with nowhere
    to go must go nowhere — not fall back to the group that does have a listener."""
    visitor = await open_visitor(assigned_conversation)
    observer = await open_supervisor(supervisor, assigned_conversation.pk)

    await observer.send_json_to({"type": "whisper", "text": WHISPER})

    assert await visitor.receive_nothing(timeout=0.8) is True

    await observer.disconnect()
    await visitor.disconnect()
