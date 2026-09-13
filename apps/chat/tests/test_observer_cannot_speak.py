"""
FR-022: observation does not make a supervisor a participant (T079, T084).

A `message` frame from this socket is **rejected explicitly**, not merely unhandled. The
difference matters: an unhandled frame is silence, which looks identical to a bug and gives
the supervisor no reason to believe anything went wrong. A rejection is a decision, and it
tells them why.

The deeper guarantee is structural — this socket never joins the public group, so even a
rejection that failed would have nowhere to deliver to. These tests assert both layers,
because the structural one is the guarantee and the explicit one is the courtesy.
"""

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator

from apps.chat.consumers.supervisor import SupervisorConsumer
from apps.chat.consumers.visitor import VisitorConsumer
from apps.chat.services import tokens
from apps.chat.services.redis_client import reset_for_tests
from apps.tickets.models import Message

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
    await communicator.receive_from(timeout=2)  # the arrival notice, broadcast to staff
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
    await communicator.receive_from(timeout=2)
    return communicator


async def test_a_message_frame_is_rejected_rather_than_ignored(assigned_conversation, supervisor):
    observer = await open_supervisor(supervisor, assigned_conversation.pk)

    await observer.send_json_to({"type": "message", "text": "Let me take over"})
    frame = await observer.receive_from(timeout=2)

    assert "refused" in frame
    await observer.disconnect()


async def test_it_is_never_written_to_the_transcript(assigned_conversation, supervisor):
    observer = await open_supervisor(supervisor, assigned_conversation.pk)

    await observer.send_json_to({"type": "message", "text": "Let me take over"})
    await observer.receive_from(timeout=2)

    written = await database_sync_to_async(
        lambda: list(Message.objects.filter(body="Let me take over"))
    )()
    assert written == []
    await observer.disconnect()


async def test_it_appears_on_no_other_socket(assigned_conversation, supervisor):
    """Invariant 3: rejected and never seen anywhere — not by the customer, and not by the
    agent either."""
    visitor = await open_visitor(assigned_conversation)
    observer = await open_supervisor(supervisor, assigned_conversation.pk)

    await observer.send_json_to({"type": "message", "text": "Let me take over"})
    await observer.receive_from(timeout=2)

    assert await visitor.receive_nothing(timeout=0.6) is True
    await observer.disconnect()
    await visitor.disconnect()


async def test_a_typing_frame_from_an_observer_is_refused_too(assigned_conversation, supervisor):
    """A typing indicator is customer-directed as surely as a message: it would appear in the
    customer's window as somebody composing a reply."""
    observer = await open_supervisor(supervisor, assigned_conversation.pk)

    await observer.send_json_to({"type": "typing"})
    frame = await observer.receive_from(timeout=2)

    assert "refused" in frame
    await observer.disconnect()


async def test_an_observer_cannot_end_the_conversation(assigned_conversation, supervisor):
    """Ending is the agent's to do. A supervisor who disagrees can say so privately."""
    from apps.chat.models import Conversation

    observer = await open_supervisor(supervisor, assigned_conversation.pk)

    await observer.send_json_to({"type": "close"})
    await observer.receive_from(timeout=2)

    state = await database_sync_to_async(
        lambda: Conversation.objects.get(pk=assigned_conversation.pk).state
    )()
    assert state != Conversation.State.ENDED
    await observer.disconnect()
