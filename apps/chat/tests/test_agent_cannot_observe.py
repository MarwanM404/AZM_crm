"""
FR-037: observation is the Supervisor's, not the Agent's (T082).

An agent with access to this socket could read any colleague's live conversation in their
department, silently and without a record they would recognise as unusual. The role check is
therefore at the handshake, and on every `/chat/supervise/` path — not in the template that
decides whether to show the link.
"""

import pytest
from channels.testing import WebsocketCommunicator
from django.urls import reverse

from apps.chat.consumers.supervisor import SupervisorConsumer
from apps.chat.models import Observation
from apps.chat.services.redis_client import reset_for_tests

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clean():
    reset_for_tests()
    yield
    reset_for_tests()


@pytest.mark.django_db(transaction=True)
async def test_an_agent_is_refused_the_supervisor_socket(assigned_conversation, agent):
    communicator = WebsocketCommunicator(
        SupervisorConsumer.as_asgi(),
        f"/ws/chat/supervise/?conversation={assigned_conversation.pk}",
    )
    communicator.scope["user"] = agent
    connected, _ = await communicator.connect()
    await communicator.disconnect()

    assert connected is False


@pytest.mark.django_db(transaction=True)
async def test_the_refusal_records_no_observation(assigned_conversation, agent):
    from channels.db import database_sync_to_async

    communicator = WebsocketCommunicator(
        SupervisorConsumer.as_asgi(),
        f"/ws/chat/supervise/?conversation={assigned_conversation.pk}",
    )
    communicator.scope["user"] = agent
    await communicator.connect()
    await communicator.disconnect()

    count = await database_sync_to_async(Observation.objects.count)()
    assert count == 0


def test_an_agent_is_refused_the_supervision_list(agent_client):
    response = agent_client.get(reverse("chat:supervise"))

    assert response.status_code in (403, 404)


def test_an_agent_is_refused_a_supervision_view(agent_client, assigned_conversation):
    response = agent_client.get(
        reverse("chat:supervise_conversation", args=[assigned_conversation.pk])
    )

    assert response.status_code in (403, 404)


def test_a_supervisor_is_allowed_both(supervisor_client, assigned_conversation):
    """The refusals above must not be passing because supervision is broken for everyone."""
    assert supervisor_client.get(reverse("chat:supervise")).status_code == 200
    assert (
        supervisor_client.get(
            reverse("chat:supervise_conversation", args=[assigned_conversation.pk])
        ).status_code
        == 200
    )
