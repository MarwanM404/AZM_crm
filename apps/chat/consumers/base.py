"""
Shared consumer behaviour.

Consumers here do transport and nothing else. Every database touch goes through
`database_sync_to_async`, and every decision about *who may see what* is made in
`apps/chat/services/` before the broadcast — so a consumer never chooses a group, never
filters a message, and cannot get either wrong.

That division is the cost ADR-007 accepted: the ORM is synchronous and consumers are not.
Keeping logic out of them is what stops that cost turning into subtle bugs.
"""

import json
import time

from channels.generic.websocket import AsyncWebsocketConsumer


class RateLimiter:
    """A token bucket per connection.

    Per-connection and in-memory on purpose: the thing being limited is one socket's traffic,
    so a Redis round trip per frame would cost more than the check is worth. A visitor with
    several sockets is limited per socket, which is acceptable — the volume that matters is
    what one connection can push.
    """

    def __init__(self, capacity=10, refill_per_second=2.0):
        self.capacity = capacity
        self.refill = refill_per_second
        self.tokens = float(capacity)
        self.checked_at = time.monotonic()

    def allow(self) -> bool:
        now = time.monotonic()
        self.tokens = min(self.capacity, self.tokens + (now - self.checked_at) * self.refill)
        self.checked_at = now
        if self.tokens < 1:
            return False
        self.tokens -= 1
        return True


class ChatConsumer(AsyncWebsocketConsumer):
    """Frame plumbing shared by all three sockets."""

    async def send_html(self, html: str) -> None:
        await self.send(text_data=html)

    async def send_event(self, **payload) -> None:
        await self.send(text_data=json.dumps(payload))

    # --- group handlers. Each forwards what the service already decided. ---

    async def chat_message(self, event):
        await self.send_html(event["html"])

    async def chat_system(self, event):
        await self.send_html(event["html"])

    async def chat_typing(self, event):
        await self.send_event(type="typing", who=event["who"])

    async def chat_unread(self, event):
        await self.send_event(type="unread", counts=event["counts"])

    async def chat_state(self, event):
        await self.send_event(
            type="state", state=event.get("state"), position=event.get("position")
        )

    async def chat_desk_closed(self, event):
        """FR-042: the desk closed while this visitor was waiting. Carries where to go and
        what they already typed, so they do not retype their question."""
        await self.send_event(
            type="desk_closed",
            fallback=event.get("fallback"),
            carry=event.get("carry") or {},
        )

    async def chat_disconnect(self, event):
        """Close this socket now — the account behind it was deactivated (MVP FR-026).

        A handshake-time authorization check cannot expire on its own, so the revocation has
        to be pushed."""
        await self.close()

    async def chat_ended(self, event):
        await self.send_event(type="ended", reference=event.get("reference"))

    @staticmethod
    def parse(text_data):
        try:
            payload = json.loads(text_data or "{}")
        except (TypeError, ValueError):
            return {}
        return payload if isinstance(payload, dict) else {}
