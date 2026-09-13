"""
FR-021: the customer is never told they are being observed (T078).

The assertion here is deliberately stronger than "no message appears". A supervisor
connecting, watching and leaving must produce **no frame of any kind** on the visitor's
socket — not a typing indicator, not a state change, not a presence event, not an empty
keep-alive. Anything at all, at the moment a supervisor joins, is a tell: a customer who
notices the pattern learns exactly when someone started listening.

That is why these tests drain the connect-time frames first and then assert silence, rather
than checking that no *message* arrived.
"""

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator

from apps.chat.consumers.supervisor import SupervisorConsumer
from apps.chat.consumers.visitor import VisitorConsumer
from apps.chat.services import messaging, tokens
from apps.chat.services.redis_client import reset_for_tests

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def clean():
    reset_for_tests()
    yield
    reset_for_tests()


async def open_visitor(conversation):
    """Open the customer's socket and drain the `state` frame sent on connect, so a later
    `receive_nothing` is measuring silence rather than reading that frame."""
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
    await communicator.receive_from(timeout=2)  # the connect-time `state` frame
    return communicator


async def open_supervisor(user, conversation_id):
    communicator = WebsocketCommunicator(
        SupervisorConsumer.as_asgi(), f"/ws/chat/supervise/?conversation={conversation_id}"
    )
    communicator.scope["user"] = user
    await communicator.connect()
    return communicator


async def test_a_supervisor_connecting_produces_no_frame_on_the_visitors_socket(
    assigned_conversation, supervisor
):
    visitor = await open_visitor(assigned_conversation)

    observer = await open_supervisor(supervisor, assigned_conversation.pk)

    assert await visitor.receive_nothing(timeout=0.5) is True
    await observer.disconnect()
    await visitor.disconnect()


async def test_a_supervisor_disconnecting_produces_no_frame_either(
    assigned_conversation, supervisor
):
    """Leaving is as much of a tell as arriving."""
    visitor = await open_visitor(assigned_conversation)
    observer = await open_supervisor(supervisor, assigned_conversation.pk)
    await visitor.receive_nothing(timeout=0.3)

    await observer.disconnect()

    assert await visitor.receive_nothing(timeout=0.5) is True
    await visitor.disconnect()


async def test_the_whisper_that_follows_reaches_no_customer_socket(
    assigned_conversation, supervisor
):
    """Invariant 1 in the contract: confirmed by the visitor receiving *nothing at all*,
    rather than by checking that what arrived was not internal."""
    visitor = await open_visitor(assigned_conversation)
    observer = await open_supervisor(supervisor, assigned_conversation.pk)

    await database_sync_to_async(messaging.whisper)(
        assigned_conversation, supervisor, "Watch your tone here"
    )

    assert await visitor.receive_nothing(timeout=0.6) is True
    await observer.disconnect()
    await visitor.disconnect()


async def test_the_customer_still_receives_their_own_conversation_normally(
    assigned_conversation, supervisor, agent
):
    """The silence must be specific to observation. A test that passes because the visitor's
    socket is broken would prove nothing, so this asserts the socket still works."""
    visitor = await open_visitor(assigned_conversation)
    observer = await open_supervisor(supervisor, assigned_conversation.pk)

    await database_sync_to_async(messaging.agent_message)(
        assigned_conversation, agent, "Thanks for waiting"
    )

    assert "Thanks for waiting" in await visitor.receive_from(timeout=2)
    await observer.disconnect()
    await visitor.disconnect()
