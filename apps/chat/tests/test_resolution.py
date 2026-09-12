"""
Ending, and whether that resolves anything (T069, T074, FR-029).

"The conversation is over" and "the problem is solved" are different facts. Conflating them
makes the resolution rate a measure of how often agents click the close button.
"""

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator

from apps.chat.consumers.agent import AgentConsumer
from apps.chat.models import Conversation
from apps.chat.services.redis_client import reset_for_tests
from apps.tickets.models import Ticket

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def clean():
    reset_for_tests()
    yield
    reset_for_tests()


async def _agent_socket(user):
    communicator = WebsocketCommunicator(AgentConsumer.as_asgi(), "/ws/chat/agent/")
    communicator.scope["user"] = user
    await communicator.connect()
    return communicator


async def test_closing_without_resolving_leaves_the_ticket_open(assigned_conversation, agent):
    communicator = await _agent_socket(agent)
    await communicator.send_json_to({"type": "close", "conversation": assigned_conversation.pk})
    await communicator.receive_nothing(timeout=0.3)

    conversation = await database_sync_to_async(
        lambda: Conversation.objects.select_related("ticket").get(pk=assigned_conversation.pk)
    )()
    assert conversation.state == Conversation.State.ENDED
    assert conversation.end_reason == Conversation.EndReason.ENDED_BY_AGENT
    assert conversation.ticket.status != Ticket.Status.RESOLVED
    await communicator.disconnect()


async def test_closing_with_resolve_resolves_the_ticket(assigned_conversation, agent):
    communicator = await _agent_socket(agent)
    await communicator.send_json_to(
        {"type": "close", "conversation": assigned_conversation.pk, "resolve": True}
    )
    await communicator.receive_nothing(timeout=0.3)

    conversation = await database_sync_to_async(
        lambda: Conversation.objects.select_related("ticket").get(pk=assigned_conversation.pk)
    )()
    assert conversation.end_reason == Conversation.EndReason.RESOLVED
    assert conversation.ticket.status == Ticket.Status.RESOLVED
    await communicator.disconnect()


async def test_an_agent_cannot_close_a_conversation_outside_their_scope(
    conversation, other_department_agent
):
    """`_conversation_for` scopes the lookup, so the close simply finds nothing — the same
    404-shaped silence the HTTP surface gives."""
    communicator = await _agent_socket(other_department_agent)
    await communicator.send_json_to({"type": "close", "conversation": conversation.pk})
    await communicator.receive_nothing(timeout=0.3)

    refreshed = await database_sync_to_async(Conversation.objects.get)(pk=conversation.pk)
    assert refreshed.state != Conversation.State.ENDED
    await communicator.disconnect()
