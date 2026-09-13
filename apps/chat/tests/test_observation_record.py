"""
FR-023: watching a colleague is a recorded act (T081, T085).

Observation is not a neutral read. A supervisor reading a live conversation is exercising
authority over an agent who cannot see them, and the only thing that makes that accountable
is a record of who watched whose conversation, and when. `Observation` is deliberately not
soft-deletable for the same reason (apps/chat/models.py) — there is no state in which this
should be hideable.
"""

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator

from apps.chat.consumers.supervisor import SupervisorConsumer
from apps.chat.models import Observation
from apps.chat.services.redis_client import reset_for_tests

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def clean():
    reset_for_tests()
    yield
    reset_for_tests()


async def open_supervisor(user, conversation_id):
    communicator = WebsocketCommunicator(
        SupervisorConsumer.as_asgi(), f"/ws/chat/supervise/?conversation={conversation_id}"
    )
    communicator.scope["user"] = user
    await communicator.connect()
    return communicator


@database_sync_to_async
def observations(conversation):
    return list(Observation.objects.filter(conversation=conversation))


async def test_connecting_opens_a_record(assigned_conversation, supervisor):
    observer = await open_supervisor(supervisor, assigned_conversation.pk)

    rows = await observations(assigned_conversation)

    assert len(rows) == 1
    assert rows[0].observer_id == supervisor.pk
    assert rows[0].started_at is not None
    assert rows[0].ended_at is None  # still watching
    await observer.disconnect()


async def test_disconnecting_closes_it(assigned_conversation, supervisor):
    observer = await open_supervisor(supervisor, assigned_conversation.pk)

    await observer.disconnect()

    rows = await observations(assigned_conversation)
    assert len(rows) == 1
    assert rows[0].ended_at is not None
    assert rows[0].ended_at >= rows[0].started_at


async def test_a_refused_connection_records_nothing(
    assigned_conversation, other_department_supervisor
):
    """A record of an observation that never happened is as misleading as a missing one."""
    communicator = WebsocketCommunicator(
        SupervisorConsumer.as_asgi(),
        f"/ws/chat/supervise/?conversation={assigned_conversation.pk}",
    )
    communicator.scope["user"] = other_department_supervisor
    connected, _ = await communicator.connect()
    await communicator.disconnect()

    assert connected is False
    assert await observations(assigned_conversation) == []


async def test_each_viewing_is_its_own_record(assigned_conversation, supervisor):
    """Two separate sittings are two facts. Collapsing them would hide how long, and how
    often, a particular agent was watched."""
    first = await open_supervisor(supervisor, assigned_conversation.pk)
    await first.disconnect()
    second = await open_supervisor(supervisor, assigned_conversation.pk)
    await second.disconnect()

    rows = await observations(assigned_conversation)
    assert len(rows) == 2
    assert all(row.ended_at is not None for row in rows)


async def test_the_record_names_the_conversation_not_merely_the_agent(
    assigned_conversation, supervisor
):
    rows_before = await observations(assigned_conversation)
    observer = await open_supervisor(supervisor, assigned_conversation.pk)
    rows = await observations(assigned_conversation)

    assert rows_before == []
    assert rows[0].conversation_id == assigned_conversation.pk
    await observer.disconnect()
