"""
Going online and offline (T052, T056).

FR-014 is the one with teeth: an agent cannot go offline while holding open conversations.
Without it, "I'm done for the day" silently abandons whoever is mid-sentence — the customer
keeps typing into a conversation nobody is reading, and nothing in the system notices.
"""

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator

from apps.chat.consumers.agent import AgentConsumer
from apps.chat.services import presence

pytestmark = pytest.mark.django_db(transaction=True)


async def open_agent(user):
    communicator = WebsocketCommunicator(AgentConsumer.as_asgi(), "/ws/chat/agent/")
    communicator.scope["user"] = user
    assert (await communicator.connect())[0]
    return communicator


async def test_going_online_then_offline_works_with_nothing_held(agent):
    communicator = await open_agent(agent)

    await communicator.send_json_to({"type": "online"})
    await communicator.receive_nothing(timeout=0.2)
    assert await database_sync_to_async(presence.is_online)(agent.pk) is True

    await communicator.send_json_to({"type": "offline"})
    await communicator.receive_json_from(timeout=2)
    assert await database_sync_to_async(presence.is_online)(agent.pk) is False

    await communicator.disconnect()


async def test_going_offline_is_refused_while_holding_a_conversation(assigned_conversation, agent):
    """The conversation is open and assigned to this agent, so they are still needed."""
    communicator = await open_agent(agent)

    await communicator.send_json_to({"type": "offline"})
    frame = await communicator.receive_json_from(timeout=2)

    assert frame["type"] == "offline_refused"
    assert frame["open"] == 1
    assert await database_sync_to_async(presence.is_online)(agent.pk) is True

    await communicator.disconnect()


async def test_the_refusal_says_how_many_are_still_open(
    assigned_conversation, agent, department, branch, category, contact
):
    """ "You still have conversations open" is unactionable; a number tells them how much is
    left before they can leave."""
    from django.utils import timezone

    from apps.chat.models import Conversation
    from apps.tickets.models import Ticket

    @database_sync_to_async
    def second_one():
        ticket = Ticket.objects.create(
            contact=contact,
            subject="Second",
            description="",
            category=category,
            origin_channel=Ticket.Channel.CHAT,
            department=department,
            branch=branch,
        )
        return Conversation.objects.create(
            ticket=ticket,
            contact=contact,
            visitor_token_hash="z" * 64,
            assigned_to=agent,
            state=Conversation.State.ACTIVE,
            assigned_at=timezone.now(),
            department=department,
            branch=branch,
        )

    await second_one()
    communicator = await open_agent(agent)
    await communicator.send_json_to({"type": "offline"})
    frame = await communicator.receive_json_from(timeout=2)

    assert frame["open"] == 2
    await communicator.disconnect()


async def test_an_offline_agent_receives_no_new_conversations(agent):
    """Presence is what assignment reads; going offline must actually remove them from it."""
    communicator = await open_agent(agent)
    await communicator.send_json_to({"type": "online"})
    await communicator.receive_nothing(timeout=0.2)
    await communicator.send_json_to({"type": "offline"})
    await communicator.receive_json_from(timeout=2)

    from apps.chat.services import lifecycle

    candidates = await database_sync_to_async(lifecycle.candidate_agents)(
        agent.department_id, agent.branch_id
    )
    assert agent.pk not in candidates
    await communicator.disconnect()
