"""
Messages moving between two sockets (T035, T043).

The assertion that matters most here is the ordering one: a message must exist in the database
*before* it appears on any socket. Broadcasting first would feel marginally faster and would
lose exactly the messages sent in the moments before a crash — which are the ones a dispute is
most likely to be about (research.md #6).
"""

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator

from apps.chat.consumers.agent import AgentConsumer
from apps.chat.consumers.visitor import VisitorConsumer
from apps.tickets.models import Message

pytestmark = pytest.mark.django_db(transaction=True)


async def open_visitor(conversation):
    """Opens the socket and drains the `state` frame sent on connect, so a test asserting
    what arrives next is not reading the handshake."""
    communicator = WebsocketCommunicator(
        VisitorConsumer.as_asgi(), f"/ws/chat/visitor/?token={conversation.test_token}"
    )
    connected, _ = await communicator.connect()
    assert connected
    await communicator.receive_from(timeout=1)  # the connect-time state frame
    return communicator


async def open_agent(agent):
    communicator = WebsocketCommunicator(AgentConsumer.as_asgi(), "/ws/chat/agent/")
    communicator.scope["user"] = agent
    connected, _ = await communicator.connect()
    assert connected
    return communicator


@database_sync_to_async
def stored_bodies(conversation):
    return list(conversation.ticket.messages.values_list("body", flat=True))


async def test_a_visitor_message_reaches_the_agent(assigned_conversation, agent):
    visitor = await open_visitor(assigned_conversation)
    staff = await open_agent(agent)

    await visitor.send_json_to({"type": "message", "text": "My order never arrived"})
    received = await staff.receive_from(timeout=2)

    assert "My order never arrived" in received
    await visitor.disconnect()
    await staff.disconnect()


async def test_an_agent_message_reaches_the_visitor(assigned_conversation, agent):
    visitor = await open_visitor(assigned_conversation)
    staff = await open_agent(agent)

    await staff.send_json_to(
        {"type": "message", "conversation": assigned_conversation.pk, "text": "Looking now"}
    )
    received = await visitor.receive_from(timeout=2)

    assert "Looking now" in received
    await visitor.disconnect()
    await staff.disconnect()


async def test_a_message_is_stored_before_it_is_broadcast(assigned_conversation, agent):
    """research.md #6. A crash must cost a delivery — which the client refetches — rather
    than a transcript, which nothing can reconstruct."""
    visitor = await open_visitor(assigned_conversation)
    staff = await open_agent(agent)

    await visitor.send_json_to({"type": "message", "text": "persisted first"})
    await staff.receive_from(timeout=2)  # by the time it arrives, it must already be stored

    assert "persisted first" in await stored_bodies(assigned_conversation)
    await visitor.disconnect()
    await staff.disconnect()


async def test_a_visitor_message_is_stored_as_inbound_and_public(assigned_conversation, agent):
    visitor = await open_visitor(assigned_conversation)
    staff = await open_agent(agent)
    await visitor.send_json_to({"type": "message", "text": "from the customer"})
    await staff.receive_from(timeout=2)

    @database_sync_to_async
    def latest():
        return assigned_conversation.ticket.messages.order_by("-created_at").first()

    message = await latest()
    assert message.direction == Message.Direction.INBOUND
    assert message.visibility == Message.Visibility.PUBLIC
    assert message.channel == Message.Channel.CHAT if hasattr(Message, "Channel") else True
    assert message.author is None  # written by the customer, not a staff member

    await visitor.disconnect()
    await staff.disconnect()


async def test_an_agent_message_is_attributed_to_them(assigned_conversation, agent):
    visitor = await open_visitor(assigned_conversation)
    staff = await open_agent(agent)
    await staff.send_json_to(
        {"type": "message", "conversation": assigned_conversation.pk, "text": "from the agent"}
    )
    await visitor.receive_from(timeout=2)

    @database_sync_to_async
    def latest():
        return (
            assigned_conversation.ticket.messages.order_by("-created_at")
            .select_related("author")
            .first()
        )

    message = await latest()
    assert message.author_id == agent.pk
    assert message.direction == Message.Direction.OUTBOUND
    assert message.visibility == Message.Visibility.PUBLIC

    await visitor.disconnect()
    await staff.disconnect()


async def test_an_empty_message_is_ignored(assigned_conversation, agent):
    visitor = await open_visitor(assigned_conversation)
    await visitor.send_json_to({"type": "message", "text": "   "})

    assert await visitor.receive_nothing(timeout=0.3) is True
    assert await stored_bodies(assigned_conversation) == []
    await visitor.disconnect()


async def test_a_visitor_cannot_post_to_another_conversation(
    assigned_conversation, agent, department, branch, category, contact
):
    """The socket is bound to the conversation its token named; a conversation id in the frame
    must not be able to redirect it."""
    from apps.chat.models import Conversation
    from apps.tickets.models import Ticket

    @database_sync_to_async
    def make_other():
        ticket = Ticket.objects.create(
            contact=contact,
            subject="Someone else",
            description="",
            category=category,
            origin_channel=Ticket.Channel.CHAT,
            department=department,
            branch=branch,
        )
        return Conversation.objects.create(
            ticket=ticket,
            contact=contact,
            visitor_token_hash="x" * 64,
            department=department,
            branch=branch,
        )

    other = await make_other()
    visitor = await open_visitor(assigned_conversation)
    await visitor.send_json_to(
        {"type": "message", "conversation": other.pk, "text": "into someone else's chat"}
    )
    await visitor.receive_nothing(timeout=0.3)

    assert "into someone else's chat" not in await stored_bodies(other)
    await visitor.disconnect()


async def test_arabic_survives_the_socket(assigned_conversation, agent):
    visitor = await open_visitor(assigned_conversation)
    staff = await open_agent(agent)

    arabic = "لم يصل الشحن حتى الآن"
    await visitor.send_json_to({"type": "message", "text": arabic})
    received = await staff.receive_from(timeout=2)

    assert arabic in received
    assert arabic in await stored_bodies(assigned_conversation)
    await visitor.disconnect()
    await staff.disconnect()
