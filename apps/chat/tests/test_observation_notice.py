"""
The agent is told they are being watched (FR-021 boundary, decision recorded in
apps/chat/consumers/supervisor.py).

FR-021 forbids telling the **customer**. The spec says nothing about the agent, and this desk
chose to tell them: the `Observation` record satisfies the audit requirement, and the live
notice is what keeps observation legible as coaching rather than surveillance.

That choice puts a new message on the staff broadcast at the exact moment a supervisor
connects — which is the moment FR-021 is most easily broken. Dropping `staff_only=True` would
deliver "Team Lead is observing this conversation" straight to the customer's window. These
tests hold both halves: the agent receives it, and the customer receives nothing at all.
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


async def open_supervisor(user, conversation_id):
    communicator = WebsocketCommunicator(
        SupervisorConsumer.as_asgi(), f"/ws/chat/supervise/?conversation={conversation_id}"
    )
    communicator.scope["user"] = user
    await communicator.connect()
    return communicator


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
    await communicator.receive_from(timeout=2)  # connect-time `state` frame
    return communicator


async def test_the_agent_is_told_when_observation_starts(assigned_conversation, agent, supervisor):
    agent_socket = await open_agent(agent)

    observer = await open_supervisor(supervisor, assigned_conversation.pk)
    frame = await agent_socket.receive_from(timeout=2)

    assert "observing this conversation" in frame
    await observer.disconnect()
    await agent_socket.disconnect()


async def test_the_notice_names_the_observer(assigned_conversation, agent, supervisor):
    """ "A supervisor is watching" invites the agent to guess which one, and guessing wrong is
    worse than knowing."""
    agent_socket = await open_agent(agent)

    observer = await open_supervisor(supervisor, assigned_conversation.pk)
    frame = await agent_socket.receive_from(timeout=2)

    assert supervisor.full_name in frame
    await observer.disconnect()
    await agent_socket.disconnect()


async def test_the_notice_says_private_notes_may_follow(assigned_conversation, agent, supervisor):
    """The agent should not be surprised by the first whisper."""
    agent_socket = await open_agent(agent)

    observer = await open_supervisor(supervisor, assigned_conversation.pk)
    frame = await agent_socket.receive_from(timeout=2)

    assert "cannot see" in frame
    await observer.disconnect()
    await agent_socket.disconnect()


async def test_the_agent_is_told_when_it_stops(assigned_conversation, agent, supervisor):
    """A "someone is watching" notice that never clears is worse than no notice — the agent
    goes on believing it after it stopped being true."""
    agent_socket = await open_agent(agent)
    observer = await open_supervisor(supervisor, assigned_conversation.pk)
    await agent_socket.receive_from(timeout=2)  # the arrival notice

    await observer.disconnect()
    frame = await agent_socket.receive_from(timeout=2)

    assert "no longer observing" in frame
    await agent_socket.disconnect()


async def test_the_customer_is_told_neither(assigned_conversation, agent, supervisor):
    """FR-021. This is the test that fails if `staff_only=True` is ever dropped."""
    visitor = await open_visitor(assigned_conversation)
    agent_socket = await open_agent(agent)

    observer = await open_supervisor(supervisor, assigned_conversation.pk)
    await agent_socket.receive_from(timeout=2)
    assert await visitor.receive_nothing(timeout=0.5) is True

    await observer.disconnect()
    await agent_socket.receive_from(timeout=2)
    assert await visitor.receive_nothing(timeout=0.5) is True

    await visitor.disconnect()
    await agent_socket.disconnect()


async def test_a_refused_observer_announces_nothing(
    assigned_conversation, agent, other_department_supervisor
):
    """An observer who was turned away at the handshake never watched, so telling the agent
    they did would be a false alarm about a colleague."""
    agent_socket = await open_agent(agent)

    refused = await open_supervisor(other_department_supervisor, assigned_conversation.pk)
    await refused.disconnect()

    assert await agent_socket.receive_nothing(timeout=0.5) is True
    await agent_socket.disconnect()
