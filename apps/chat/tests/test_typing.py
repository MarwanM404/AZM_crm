"""Typing indicators (T036, T044). Transient: never persisted, because a typing indicator is
not part of the transcript."""

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator

from apps.chat.consumers.agent import AgentConsumer
from apps.chat.consumers.visitor import VisitorConsumer

pytestmark = pytest.mark.django_db(transaction=True)


async def open_visitor(conversation):
    c = WebsocketCommunicator(
        VisitorConsumer.as_asgi(), f"/ws/chat/visitor/?token={conversation.test_token}"
    )
    assert (await c.connect())[0]
    await c.receive_from(timeout=1)  # the connect-time state frame
    return c


async def open_agent(agent):
    c = WebsocketCommunicator(AgentConsumer.as_asgi(), "/ws/chat/agent/")
    c.scope["user"] = agent
    assert (await c.connect())[0]
    return c


async def test_the_agent_sees_the_visitor_typing(assigned_conversation, agent):
    visitor = await open_visitor(assigned_conversation)
    staff = await open_agent(agent)

    await visitor.send_json_to({"type": "typing"})
    frame = await staff.receive_json_from(timeout=2)

    assert frame["type"] == "typing"
    assert frame["who"] == "visitor"
    await visitor.disconnect()
    await staff.disconnect()


async def test_the_visitor_sees_the_agent_typing(assigned_conversation, agent):
    visitor = await open_visitor(assigned_conversation)
    staff = await open_agent(agent)

    await staff.send_json_to({"type": "typing", "conversation": assigned_conversation.pk})
    frame = await visitor.receive_json_from(timeout=2)

    assert frame["type"] == "typing"
    assert frame["who"] == "agent"
    await visitor.disconnect()
    await staff.disconnect()


async def test_typing_is_never_written_to_the_transcript(assigned_conversation, agent):
    """A conversation is a record of what was said, not of what was nearly said."""
    visitor = await open_visitor(assigned_conversation)
    staff = await open_agent(agent)

    for _ in range(5):
        await visitor.send_json_to({"type": "typing"})
    await staff.receive_json_from(timeout=2)

    @database_sync_to_async
    def count():
        return assigned_conversation.ticket.messages.count()

    assert await count() == 0
    await visitor.disconnect()
    await staff.disconnect()
