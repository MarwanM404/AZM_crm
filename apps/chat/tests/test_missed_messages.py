"""
Nothing said in the gap is lost (T114, T119, FR-035).

The replay is read from the database, never from a buffer held in the process. That choice is
the whole point of the test below that restarts nothing and still finds the message: a buffer
would satisfy the happy path and lose exactly the messages a crash was in the middle of, which
are the ones a dispute is most likely to be about.
"""

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator

from apps.chat.consumers.visitor import VisitorConsumer
from apps.chat.services import messaging
from apps.chat.services.redis_client import reset_for_tests

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def clean():
    reset_for_tests()
    yield
    reset_for_tests()


async def open_visitor(conversation):
    communicator = WebsocketCommunicator(
        VisitorConsumer.as_asgi(), f"/ws/chat/visitor/?token={conversation.test_token}"
    )
    await communicator.connect()
    return communicator


async def drain(communicator, timeout=0.6):
    frames = []
    while not await communicator.receive_nothing(timeout=timeout):
        frames.append(await communicator.receive_from(timeout=timeout))
    return frames


async def test_a_message_sent_while_away_arrives_on_return(assigned_conversation, agent):
    first = await open_visitor(assigned_conversation)
    await drain(first)
    await first.disconnect()

    await database_sync_to_async(messaging.agent_message)(
        assigned_conversation, agent, "Your refund is approved"
    )

    second = await open_visitor(assigned_conversation)
    frames = await drain(second)

    assert any("Your refund is approved" in frame for frame in frames)
    await second.disconnect()


async def test_several_missed_messages_arrive_in_order(assigned_conversation, agent):
    for text in ("First while away", "Second while away", "Third while away"):
        await database_sync_to_async(messaging.agent_message)(assigned_conversation, agent, text)

    communicator = await open_visitor(assigned_conversation)
    frames = await drain(communicator)

    joined = " ".join(frames)
    assert joined.index("First while away") < joined.index("Second while away")
    assert joined.index("Second while away") < joined.index("Third while away")
    await communicator.disconnect()


async def test_the_replay_comes_from_the_database_not_a_buffer(assigned_conversation, agent):
    """Written straight to the database, bypassing every broadcast path, and still replayed.

    A process-local buffer would fail this — which is the point: it is a message no socket ever
    saw, the shape of what a crash leaves behind.
    """
    from apps.tickets.models import Message, Ticket

    @database_sync_to_async
    def write_directly():
        Message.objects.create(
            ticket=assigned_conversation.ticket,
            author=agent,
            direction=Message.Direction.OUTBOUND,
            visibility=Message.Visibility.PUBLIC,
            channel=Ticket.Channel.CHAT,
            body="Written with no socket in sight",
        )

    await write_directly()

    communicator = await open_visitor(assigned_conversation)
    frames = await drain(communicator)

    assert any("Written with no socket in sight" in frame for frame in frames)
    await communicator.disconnect()


async def test_the_customers_own_messages_come_back_too(assigned_conversation):
    """A thread showing only the agent's half reads as though the customer was never heard."""
    await database_sync_to_async(messaging.visitor_message)(
        assigned_conversation, "Here is my order number"
    )

    communicator = await open_visitor(assigned_conversation)
    frames = await drain(communicator)

    assert any("Here is my order number" in frame for frame in frames)
    await communicator.disconnect()


async def test_the_replay_does_not_reach_anybody_else(assigned_conversation, agent):
    """It is rendered for one socket and sent to it directly, never broadcast. A replay that
    went to the group would repeat the whole conversation into the agent's window every time
    the customer's train went through a tunnel.
    """
    from apps.chat.consumers.agent import AgentConsumer

    await database_sync_to_async(messaging.agent_message)(
        assigned_conversation, agent, "Said before the drop"
    )

    agent_socket = WebsocketCommunicator(AgentConsumer.as_asgi(), "/ws/chat/agent/")
    agent_socket.scope["user"] = agent
    await agent_socket.connect()
    await drain(agent_socket)

    visitor = await open_visitor(assigned_conversation)
    await drain(visitor)

    assert await agent_socket.receive_nothing(timeout=0.5) is True
    await visitor.disconnect()
    await agent_socket.disconnect()
