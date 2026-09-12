"""
Rate limiting (T039, T045).

Throttle, never disconnect. A customer typing quickly is not an attacker, and dropping their
connection would lose the conversation — which is a worse outcome than the flood it prevents.
"""

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator

from apps.chat.consumers.base import RateLimiter
from apps.chat.consumers.visitor import VisitorConsumer

pytestmark = pytest.mark.django_db(transaction=True)


def test_the_bucket_allows_a_burst_then_refuses():
    limiter = RateLimiter(capacity=3, refill_per_second=0)
    assert [limiter.allow() for _ in range(4)] == [True, True, True, False]


def test_the_bucket_refills_over_time(monkeypatch):
    limiter = RateLimiter(capacity=1, refill_per_second=10)
    assert limiter.allow() is True
    assert limiter.allow() is False

    import time as time_module

    start = time_module.monotonic()
    monkeypatch.setattr("apps.chat.consumers.base.time.monotonic", lambda: start + 1.0)
    assert limiter.allow() is True


async def test_a_flood_is_throttled_without_dropping_the_connection(assigned_conversation):
    communicator = WebsocketCommunicator(
        VisitorConsumer.as_asgi(),
        f"/ws/chat/visitor/?token={assigned_conversation.test_token}",
    )
    assert (await communicator.connect())[0]
    await communicator.receive_from(timeout=1)

    for i in range(40):
        await communicator.send_json_to({"type": "message", "text": f"flood {i}"})

    # Still connected, and told why some were refused.
    await communicator.send_json_to({"type": "message", "text": "still here"})
    assert await communicator.receive_nothing(timeout=0.1) in (True, False)

    @database_sync_to_async
    def stored():
        return assigned_conversation.ticket.messages.count()

    saved = await stored()
    assert saved < 40, "the flood was not throttled at all"
    assert saved > 0, "throttling rejected everything, including the first messages"

    await communicator.disconnect()
