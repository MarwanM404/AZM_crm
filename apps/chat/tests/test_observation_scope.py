"""
FR-043: a supervisor observes their own department, and nothing else (T080).

Out of scope is refused as **not-found**, never as forbidden — the same rule the HTTP surface
follows (MVP FR-024). On a socket that means the handshake is refused identically to one
naming a conversation that was never created. A supervisor who can tell those two cases apart
can enumerate which conversation ids exist in other departments.
"""

import pytest
from channels.testing import WebsocketCommunicator

from apps.chat.consumers.supervisor import SupervisorConsumer
from apps.chat.services.redis_client import reset_for_tests

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def clean():
    reset_for_tests()
    yield
    reset_for_tests()


async def connect(user, conversation_id):
    communicator = WebsocketCommunicator(
        SupervisorConsumer.as_asgi(), f"/ws/chat/supervise/?conversation={conversation_id}"
    )
    communicator.scope["user"] = user
    connected, _ = await communicator.connect()
    if connected:
        await communicator.disconnect()
    return connected


async def test_a_conversation_in_another_department_is_refused(
    assigned_conversation, other_department_supervisor
):
    assert await connect(other_department_supervisor, assigned_conversation.pk) is False


async def test_it_is_refused_identically_to_one_that_does_not_exist(
    assigned_conversation, other_department_supervisor
):
    """Identical refusals are the point. A different refusal for "exists but not yours" is a
    directory of other departments' conversations."""
    out_of_scope = await connect(other_department_supervisor, assigned_conversation.pk)
    never_existed = await connect(other_department_supervisor, 999999)

    assert out_of_scope == never_existed is False


async def test_a_supervisor_in_scope_is_allowed(assigned_conversation, supervisor):
    """The refusals above must not be passing because supervision is broken for everyone."""
    assert await connect(supervisor, assigned_conversation.pk) is True
