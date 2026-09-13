"""
The same conversation, resumed (T111, T117, T119, FR-032, FR-035).

A phone goes into a tunnel. The socket dies; the conversation does not. When the visitor comes
back within the grace period they present the same token, land in the same conversation, and
see everything that was said — including whatever the agent typed while they were away.

The history is read from the database, never from a buffer held in the process (T119). A
buffer is exactly what a crash loses, and a crash is one of the things this feature exists to
survive.
"""

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator

from apps.chat.consumers.visitor import VisitorConsumer
from apps.chat.models import Conversation
from apps.chat.services import liveness, messaging
from apps.chat.services.redis_client import reset_for_tests

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def clean():
    reset_for_tests()
    yield
    reset_for_tests()


async def open_visitor(conversation, token=None):
    token = token or conversation.test_token
    communicator = WebsocketCommunicator(
        VisitorConsumer.as_asgi(), f"/ws/chat/visitor/?token={token}"
    )
    connected, _ = await communicator.connect()
    return communicator, connected


async def drain(communicator, timeout=0.6):
    """Read every frame currently queued.

    Asks `receive_nothing` first rather than catching the timeout from `receive_from`:
    `CancelledError` is a BaseException, so `except Exception` silently fails to catch it and
    the test dies with a traceback that says nothing about what it was checking.
    """
    frames = []
    while not await communicator.receive_nothing(timeout=timeout):
        frames.append(await communicator.receive_from(timeout=timeout))
    return frames


async def test_the_same_token_resumes_the_same_conversation(assigned_conversation):
    first, _ = await open_visitor(assigned_conversation)
    await first.disconnect()

    second, connected = await open_visitor(assigned_conversation)

    assert connected is True
    await second.disconnect()


async def test_reconnecting_replays_the_history(assigned_conversation, agent):
    await database_sync_to_async(messaging.visitor_message)(
        assigned_conversation, "Where is my order?"
    )
    await database_sync_to_async(messaging.agent_message)(
        assigned_conversation, agent, "Let me look that up"
    )

    communicator, _ = await open_visitor(assigned_conversation)
    frames = await drain(communicator)

    joined = " ".join(frames)
    assert "Where is my order?" in joined
    assert "Let me look that up" in joined
    await communicator.disconnect()


async def test_what_was_said_while_away_is_delivered(assigned_conversation, agent):
    """FR-035. The agent kept working; the customer must not come back to a gap."""
    first, _ = await open_visitor(assigned_conversation)
    await drain(first, timeout=0.4)
    await first.disconnect()

    await database_sync_to_async(messaging.agent_message)(
        assigned_conversation, agent, "I found it — it ships tomorrow"
    )

    second, _ = await open_visitor(assigned_conversation)
    frames = await drain(second)

    assert any("ships tomorrow" in frame for frame in frames)
    await second.disconnect()


async def test_the_replay_never_includes_a_private_note(assigned_conversation, agent, supervisor):
    """The replay is a second path to the customer's screen, so it needs the same boundary as
    the first. A history replay that read staff messages would leak every whisper at once."""
    await database_sync_to_async(messaging.whisper)(
        assigned_conversation, supervisor, "Do not promise a refund"
    )
    await database_sync_to_async(messaging.agent_message)(
        assigned_conversation, agent, "One moment please"
    )

    communicator, _ = await open_visitor(assigned_conversation)
    frames = await drain(communicator)

    joined = " ".join(frames)
    assert "One moment please" in joined
    assert "Do not promise a refund" not in joined
    await communicator.disconnect()


async def test_a_different_token_does_not_reach_the_conversation(assigned_conversation):
    """The token is the visitor's only credential (research.md #5). Resumption must not weaken
    that: anyone presenting a token for another conversation is refused, reconnecting or not."""
    from apps.chat.services import tokens

    other = await database_sync_to_async(tokens.issue)(999999)

    communicator, connected = await open_visitor(assigned_conversation, token=other)

    assert connected is False
    await communicator.disconnect()


async def test_an_ended_conversation_is_not_resumed(assigned_conversation, agent):
    """Past the grace period the conversation is over. Presenting the old token reaches a
    conversation that no longer exists to join."""
    from apps.chat.services import lifecycle

    await database_sync_to_async(lifecycle.end)(
        assigned_conversation, reason=Conversation.EndReason.VISITOR_DISCONNECTED
    )

    communicator, connected = await open_visitor(assigned_conversation)

    assert connected is False
    await communicator.disconnect()


async def test_connecting_marks_the_visitor_present(assigned_conversation):
    """What the sweep reads. Without this a connected visitor is swept as gone."""
    communicator, _ = await open_visitor(assigned_conversation)

    assert await database_sync_to_async(liveness.present)(
        assigned_conversation.pk, liveness.VISITOR
    )
    await communicator.disconnect()


async def test_a_heartbeat_keeps_them_present(assigned_conversation):
    """The grace period restarts on every sign of life, so a long silent read does not look
    like a dropped connection."""
    import asyncio

    from apps.chat.services.redis_client import get_client

    communicator, _ = await open_visitor(assigned_conversation)
    await drain(communicator)  # the connect frames, so the wait below is a real wait
    await database_sync_to_async(get_client().force_expire)(
        f"chat:live:{assigned_conversation.pk}:visitor"
    )
    assert not await database_sync_to_async(liveness.present)(
        assigned_conversation.pk, liveness.VISITOR
    )

    await communicator.send_json_to({"type": "heartbeat"})
    await asyncio.sleep(0.3)

    assert await database_sync_to_async(liveness.present)(
        assigned_conversation.pk, liveness.VISITOR
    )
    await communicator.disconnect()


def test_both_clients_send_a_heartbeat():
    """The server treats silence as absence (FR-033), so a client that never speaks is a
    customer who gets closed on while reading.

    Asserted on the source because the behaviour lives in a timer: the visitor widget had no
    heartbeat at all until this was written, and nothing in the Python suite could have
    noticed — the sweep would simply have ended live conversations in production.
    """
    from pathlib import Path

    static = Path(__file__).resolve().parents[3] / "static" / "js"
    for name in ("chat-widget.js", "chat-console.js"):
        source = (static / name).read_text()
        assert '"heartbeat"' in source, f"{name} never tells the server it is still there"
        assert "setInterval" in source, f"{name} sends no periodic heartbeat"
