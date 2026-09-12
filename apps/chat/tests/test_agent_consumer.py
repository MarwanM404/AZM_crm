"""
The agent's socket (T034, T042).

One socket per agent rather than one per conversation, and it joins **both** groups for each
conversation they hold — public, so they see what the customer sees, and staff, so they
receive a supervisor's private notes. The visitor joins only the first. That asymmetry is the
whole boundary.
"""

import pytest
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator

from apps.chat.consumers.agent import AgentConsumer
from apps.chat.services import groups

pytestmark = pytest.mark.django_db(transaction=True)


async def open_agent(user):
    communicator = WebsocketCommunicator(AgentConsumer.as_asgi(), "/ws/chat/agent/")
    communicator.scope["user"] = user
    connected, _ = await communicator.connect()
    return communicator, connected


async def test_an_authenticated_agent_connects(agent):
    communicator, connected = await open_agent(agent)
    assert connected is True
    await communicator.disconnect()


async def test_an_anonymous_socket_is_refused():
    from django.contrib.auth.models import AnonymousUser

    communicator, connected = await open_agent(AnonymousUser())
    assert connected is False


async def test_a_supervisor_may_also_hold_conversations(department, branch):
    """A Supervisor works tickets like an Agent (FR-037), so they can take chats too."""
    from apps.accounts.models import User

    @database_sync_to_async
    def make():
        return User.objects.create_user(
            email="lead2@example.com",
            password="pw",
            full_name="Lead",
            role=User.Role.SUPERVISOR,
            department=department,
            branch=branch,
        )

    communicator, connected = await open_agent(await make())
    assert connected is True
    await communicator.disconnect()


async def test_the_agent_joins_both_groups_for_a_held_conversation(assigned_conversation, agent):
    communicator, connected = await open_agent(agent)
    assert connected

    layer = get_channel_layer()

    await layer.group_send(
        groups.public_group(assigned_conversation.pk),
        {"type": "chat.message", "html": "<div>PUBLIC</div>"},
    )
    assert "PUBLIC" in await communicator.receive_from(timeout=2)

    await layer.group_send(
        groups.staff_group(assigned_conversation.pk),
        {"type": "chat.message", "html": "<div>STAFF</div>"},
    )
    assert "STAFF" in await communicator.receive_from(timeout=2)

    await communicator.disconnect()


async def test_an_agent_does_not_receive_another_agents_conversation(
    assigned_conversation, other_agent
):
    """Joining is by what you hold, not by being staff."""
    communicator, connected = await open_agent(other_agent)
    assert connected

    await get_channel_layer().group_send(
        groups.staff_group(assigned_conversation.pk),
        {"type": "chat.message", "html": "<div>NOT YOURS</div>"},
    )
    assert await communicator.receive_nothing(timeout=0.3) is True
    await communicator.disconnect()


async def test_a_reply_to_an_out_of_scope_conversation_is_ignored(
    assigned_conversation, other_department_agent
):
    """MVP FR-024 reaches the socket too: a conversation in another department is not
    reachable by naming it in a frame."""
    communicator, connected = await open_agent(other_department_agent)
    assert connected

    await communicator.send_json_to(
        {"type": "message", "conversation": assigned_conversation.pk, "text": "intruding"}
    )

    @database_sync_to_async
    def bodies():
        return list(assigned_conversation.ticket.messages.values_list("body", flat=True))

    assert "intruding" not in await bodies()
    await communicator.disconnect()


async def test_going_online_makes_the_agent_available(agent):
    from apps.chat.services import presence

    communicator, connected = await open_agent(agent)
    assert connected

    await communicator.send_json_to({"type": "online"})
    await communicator.receive_nothing(timeout=0.2)

    assert await database_sync_to_async(presence.is_online)(agent.pk) is True
    await communicator.disconnect()


async def test_a_heartbeat_keeps_them_online(agent):
    from apps.chat.services import presence

    communicator, connected = await open_agent(agent)
    await communicator.send_json_to({"type": "online"})
    await communicator.receive_nothing(timeout=0.2)
    await communicator.send_json_to({"type": "heartbeat"})
    await communicator.receive_nothing(timeout=0.2)

    assert await database_sync_to_async(presence.is_online)(agent.pk) is True
    await communicator.disconnect()
