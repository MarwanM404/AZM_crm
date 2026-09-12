"""
The visitor's socket (T033, T041).

A visitor is anonymous, so the token *is* the authorization. Everything below is either about
proving the token is required, or about the group the socket joins — because that membership,
not any filter, is what keeps a whisper away from them.
"""

import pytest
from channels.testing import WebsocketCommunicator

from apps.chat.consumers.visitor import VisitorConsumer
from apps.chat.models import Conversation
from apps.chat.services import groups, tokens

pytestmark = pytest.mark.django_db(transaction=True)


async def connect_visitor(token):
    communicator = WebsocketCommunicator(
        VisitorConsumer.as_asgi(), f"/ws/chat/visitor/?token={token}"
    )
    connected, _ = await communicator.connect()
    return communicator, connected


async def test_a_valid_token_connects(conversation):
    communicator, connected = await connect_visitor(conversation.test_token)
    assert connected is True
    await communicator.disconnect()


@pytest.mark.parametrize("bad", ["", "not-a-token", "x.y.z"])
async def test_an_invalid_token_is_refused(conversation, bad):
    communicator, connected = await connect_visitor(bad)
    assert connected is False


async def test_a_token_for_another_conversation_is_refused(conversation):
    """A signed token is not enough — it must name *this* conversation and match its stored
    hash, or one visitor's token would open another's socket."""
    communicator, connected = await connect_visitor(tokens.issue(conversation.pk + 999))
    assert connected is False


async def test_a_token_whose_hash_does_not_match_is_refused(conversation):
    from channels.db import database_sync_to_async

    @database_sync_to_async
    def scramble():
        conversation.visitor_token_hash = "0" * 64
        conversation.save(update_fields=["visitor_token_hash"])

    await scramble()
    communicator, connected = await connect_visitor(conversation.test_token)
    assert connected is False


async def test_an_ended_conversation_is_refused(conversation):
    from channels.db import database_sync_to_async

    @database_sync_to_async
    def end_it():
        conversation.state = Conversation.State.ENDED
        conversation.save(update_fields=["state"])

    await end_it()
    communicator, connected = await connect_visitor(conversation.test_token)
    assert connected is False


async def test_the_visitor_joins_the_public_group_and_not_the_staff_group(conversation):
    """The boundary, asserted directly: publish to each group and see which arrives."""
    from channels.layers import get_channel_layer

    communicator, connected = await connect_visitor(conversation.test_token)
    assert connected

    # Drain the state frame sent on connect. Without this, `receive_nothing` below would see
    # that queued frame and report a leak that has not happened — a false alarm on the one
    # test whose failure would matter most.
    assert "state" in await communicator.receive_from(timeout=1)

    layer = get_channel_layer()
    await layer.group_send(
        groups.staff_group(conversation.pk),
        {"type": "chat.message", "html": "<div>STAFF ONLY</div>"},
    )
    assert await communicator.receive_nothing(timeout=0.3) is True

    await layer.group_send(
        groups.public_group(conversation.pk),
        {"type": "chat.message", "html": "<div>PUBLIC</div>"},
    )
    received = await communicator.receive_from(timeout=1)
    assert "PUBLIC" in received
    assert "STAFF ONLY" not in received

    await communicator.disconnect()
