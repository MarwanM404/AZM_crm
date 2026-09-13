"""
The customer's socket (FR-005, FR-006).

Authorized by a signed token naming exactly one conversation — the visitor is anonymous, so
there is no session and the token *is* the authorization.

**Joins the public group only.** Never the staff group. That membership is what keeps a
supervisor's private note away from them: not a filter that could be forgotten, but the
absence of any route from the whisper to this socket.
"""

from urllib.parse import parse_qs

from channels.db import database_sync_to_async

from apps.chat.consumers.base import ChatConsumer, RateLimiter
from apps.chat.models import Conversation
from apps.chat.services import groups, liveness, messaging, tokens


class VisitorConsumer(ChatConsumer):
    async def connect(self):
        token = self._token_from_scope()
        self.conversation = await self._authorize(token)
        if self.conversation is None:
            await self.close()
            return

        self.limiter = RateLimiter()
        await self._still_here()
        # The public group, and only the public group.
        await self.channel_layer.group_add(
            groups.public_group(self.conversation.pk), self.channel_name
        )
        await self.accept()
        await self.send_event(type="state", state=self.conversation.state)

        # A reconnection is indistinguishable from a first connection here, and deliberately
        # so: both want the conversation as it stands (FR-032, FR-035). Replaying to someone
        # who has seen nothing costs one render of an empty list.
        for html in await self._history():
            await self.send_html(html)

    async def disconnect(self, code):
        conversation = getattr(self, "conversation", None)
        if conversation is not None:
            await self.channel_layer.group_discard(
                groups.public_group(conversation.pk), self.channel_name
            )

    async def receive(self, text_data=None, bytes_data=None):
        payload = self.parse(text_data)
        kind = payload.get("type")

        # Any frame is a sign of life, so the grace period restarts. A long silent read of a
        # reply should not look like a dropped connection.
        await self._still_here()

        if not self.limiter.allow():
            # Throttle rather than disconnect: a customer typing quickly is not an attacker,
            # and dropping their connection would lose the conversation.
            await self.send_event(type="throttled")
            return

        if kind == "message":
            await self._record(payload.get("text", ""))
        elif kind == "typing":
            await self._typing()
        elif kind == "close":
            await self._close_conversation()
        elif kind == "heartbeat":
            pass  # already recorded above; the frame exists to say nothing but "still here"

    # --- everything below touches the database, so it is sync work behind the boundary ---

    def _token_from_scope(self) -> str:
        query = parse_qs((self.scope.get("query_string") or b"").decode())
        return (query.get("token") or [""])[0]

    @database_sync_to_async
    def _authorize(self, token):
        """A signed token is not enough: it must name this conversation, match the stored
        hash, and the conversation must still be open."""
        conversation_id = tokens.read(token)
        if conversation_id is None:
            return None
        conversation = (
            Conversation.objects.filter(pk=conversation_id)
            .select_related("ticket", "contact")
            .first()
        )
        if conversation is None or not conversation.is_open:
            return None
        if not tokens.matches(token, conversation.visitor_token_hash):
            return None
        return conversation

    @database_sync_to_async
    def _history(self):
        return messaging.history_for_visitor(self.conversation)

    @database_sync_to_async
    def _still_here(self):
        liveness.seen(self.conversation.pk, liveness.VISITOR)

    @database_sync_to_async
    def _record(self, text):
        # The conversation is the one the token named. A conversation id in the frame is
        # ignored entirely, so a crafted frame cannot post into someone else's chat.
        messaging.visitor_message(self.conversation, text)

    @database_sync_to_async
    def _typing(self):
        messaging.broadcast_typing(self.conversation, who="visitor")

    @database_sync_to_async
    def _close_conversation(self):
        from apps.chat.services import lifecycle

        lifecycle.end(self.conversation, reason=Conversation.EndReason.ENDED_BY_VISITOR)
