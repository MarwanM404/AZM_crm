"""
The supervisor's socket (T077, T083, contracts/websocket.md).

The whole design rests on one asymmetry: this socket joins `chat.<id>.staff` and **not**
`chat.<id>.public`. An observer is therefore not a participant, and cannot become one by
accident — there is no route from this socket to the customer, rather than a filter somewhere
that could be forgotten.
"""

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator

from apps.chat.consumers.supervisor import SupervisorConsumer
from apps.chat.services import messaging
from apps.chat.services.redis_client import reset_for_tests

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def clean():
    reset_for_tests()
    yield
    reset_for_tests()


async def open_supervisor(user, conversation_id):
    """Open the socket and drain the arrival notice.

    Connecting broadcasts "X is observing this conversation" to the staff group, and this
    socket is a member of that group — so it receives its own announcement. Draining it here
    keeps every later `receive_from` and `receive_nothing` measuring what the test is about.
    """
    communicator = WebsocketCommunicator(
        SupervisorConsumer.as_asgi(), f"/ws/chat/supervise/?conversation={conversation_id}"
    )
    communicator.scope["user"] = user
    connected, _ = await communicator.connect()
    if connected:
        await communicator.receive_from(timeout=2)
    return communicator, connected


async def test_a_supervisor_in_scope_connects(assigned_conversation, supervisor):
    communicator, connected = await open_supervisor(supervisor, assigned_conversation.pk)
    assert connected is True
    await communicator.disconnect()


async def test_an_anonymous_socket_is_refused(assigned_conversation):
    from django.contrib.auth.models import AnonymousUser

    communicator, connected = await open_supervisor(AnonymousUser(), assigned_conversation.pk)
    assert connected is False
    await communicator.disconnect()


async def test_a_conversation_that_does_not_exist_is_refused(supervisor):
    communicator, connected = await open_supervisor(supervisor, 999999)
    assert connected is False
    await communicator.disconnect()


async def test_a_missing_conversation_id_is_refused(supervisor):
    communicator = WebsocketCommunicator(SupervisorConsumer.as_asgi(), "/ws/chat/supervise/")
    communicator.scope["user"] = supervisor
    connected, _ = await communicator.connect()
    assert connected is False
    await communicator.disconnect()


async def test_it_joins_the_staff_group_and_not_the_public_one(
    assigned_conversation, supervisor, agent
):
    """The asymmetry, asserted directly: an internal message reaches this socket, and the
    socket is absent from the group the customer's messages would reach it through."""
    communicator, _ = await open_supervisor(supervisor, assigned_conversation.pk)

    await database_sync_to_async(messaging.whisper)(
        assigned_conversation, supervisor, "Only staff see this"
    )
    frame = await communicator.receive_from(timeout=2)

    assert "Only staff see this" in frame
    await communicator.disconnect()


async def test_public_messages_are_seen_too(assigned_conversation, supervisor, agent):
    """FR-020: the supervisor reads the conversation, which means everything in it — the
    staff group receives public messages as well, rendered for staff."""
    communicator, _ = await open_supervisor(supervisor, assigned_conversation.pk)

    await database_sync_to_async(messaging.visitor_message)(
        assigned_conversation, "What the customer said"
    )
    frame = await communicator.receive_from(timeout=2)

    assert "What the customer said" in frame
    await communicator.disconnect()


async def test_a_public_message_arrives_exactly_once(assigned_conversation, supervisor, agent):
    """Membership of the staff group only, asserted where it is actually observable.

    The staff group already receives public messages, so joining the public group *as well*
    changes nothing about what an observer can see or do — it silently delivers every public
    message twice. That is the failure this catches: a mutation adding the public group to
    apps/chat/consumers/supervisor.py passed every other test in this phase.
    """
    communicator, _ = await open_supervisor(supervisor, assigned_conversation.pk)

    await database_sync_to_async(messaging.visitor_message)(assigned_conversation, "Said once")

    assert "Said once" in await communicator.receive_from(timeout=2)
    assert await communicator.receive_nothing(timeout=0.4) is True
    await communicator.disconnect()


async def test_the_end_of_the_conversation_reaches_the_observer(
    assigned_conversation, supervisor, agent
):
    """FR-020: the observer follows the conversation to its end, rather than being left
    watching a window that has quietly stopped changing."""
    from apps.chat.models import Conversation
    from apps.chat.services import lifecycle

    communicator, _ = await open_supervisor(supervisor, assigned_conversation.pk)

    await database_sync_to_async(lifecycle.end)(
        assigned_conversation, reason=Conversation.EndReason.ENDED_BY_AGENT, ended_by=agent
    )

    # end() broadcasts the system notice first, then the `ended` event.
    frames = [await communicator.receive_from(timeout=2) for _unused in range(2)]

    assert any("ended" in frame for frame in frames)
    await communicator.disconnect()


async def test_disconnecting_leaves_the_staff_group(assigned_conversation, supervisor):
    """A socket left in the group after disconnect keeps receiving private notes on a channel
    nobody is reading. Reconnecting and receiving exactly one copy is what proves the old
    membership is gone — two copies would mean the first socket is still a member.
    """
    first, _ = await open_supervisor(supervisor, assigned_conversation.pk)
    await first.disconnect()

    second, _ = await open_supervisor(supervisor, assigned_conversation.pk)
    await database_sync_to_async(messaging.whisper)(
        assigned_conversation, supervisor, "Exactly once"
    )

    assert "Exactly once" in await second.receive_from(timeout=2)
    assert await second.receive_nothing(timeout=0.4) is True
    await second.disconnect()
