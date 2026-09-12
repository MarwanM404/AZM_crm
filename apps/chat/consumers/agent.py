"""
The agent's socket (FR-006, FR-011, FR-013).

One socket per agent, not one per conversation: an agent holds several at once, and a socket
each would mean reconnecting every time one is assigned.

Joins **both** groups for every conversation they hold — the public one, so they see what the
customer sees, and the staff one, so they receive a supervisor's private notes. The visitor's
socket joins only the first, which is the whole boundary.
"""

from channels.db import database_sync_to_async

from apps.accounts.models import User
from apps.chat.consumers.base import ChatConsumer, RateLimiter
from apps.chat.models import Conversation
from apps.chat.services import groups, messaging, presence

STAFF_ROLES = {User.Role.AGENT, User.Role.SUPERVISOR, User.Role.ADMINISTRATOR}


class AgentConsumer(ChatConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated or user.role not in STAFF_ROLES:
            await self.close()
            return

        self.user = user
        self.limiter = RateLimiter(capacity=30, refill_per_second=5.0)
        self.joined: set[int] = set()

        # Their own group, for assignment offers that are not tied to a conversation yet.
        await self.channel_layer.group_add(self._personal_group(), self.channel_name)

        for conversation_id in await self._held_conversation_ids():
            await self._join_conversation(conversation_id)

        await self.accept()

    async def disconnect(self, code):
        if not hasattr(self, "user"):
            return
        await self.channel_layer.group_discard(self._personal_group(), self.channel_name)
        for conversation_id in list(self.joined):
            await self._leave_conversation(conversation_id)

    async def receive(self, text_data=None, bytes_data=None):
        payload = self.parse(text_data)
        kind = payload.get("type")

        if not self.limiter.allow():
            await self.send_event(type="throttled")
            return

        if kind == "message":
            await self._reply(payload.get("conversation"), payload.get("text", ""))
        elif kind == "typing":
            await self._typing(payload.get("conversation"))
        elif kind == "heartbeat":
            await self._heartbeat()
        elif kind == "online":
            await self._go_online()
        elif kind == "offline":
            await self._go_offline()

    # --- group membership ---

    def _personal_group(self) -> str:
        return f"chat.agent.{self.user.pk}"

    async def _join_conversation(self, conversation_id: int) -> None:
        await self.channel_layer.group_add(groups.public_group(conversation_id), self.channel_name)
        await self.channel_layer.group_add(groups.staff_group(conversation_id), self.channel_name)
        self.joined.add(int(conversation_id))

    async def _leave_conversation(self, conversation_id: int) -> None:
        await self.channel_layer.group_discard(
            groups.public_group(conversation_id), self.channel_name
        )
        await self.channel_layer.group_discard(
            groups.staff_group(conversation_id), self.channel_name
        )
        self.joined.discard(int(conversation_id))

    async def chat_assigned(self, event):
        """A conversation was handed to this agent while they were connected."""
        await self._join_conversation(event["conversation"])
        await self.send_event(type="assigned", conversation=event["conversation"])

    # --- database work, behind the boundary ---

    @database_sync_to_async
    def _held_conversation_ids(self):
        return list(
            Conversation.objects.filter(
                assigned_to=self.user, state=Conversation.State.ACTIVE
            ).values_list("pk", flat=True)
        )

    @database_sync_to_async
    def _conversation_for(self, conversation_id):
        """Scoped like every other lookup in this product: a conversation outside the agent's
        department is not found rather than forbidden (MVP FR-024)."""
        if conversation_id is None:
            return None
        return (
            Conversation.objects.for_user(self.user)
            .filter(pk=conversation_id)
            .select_related("ticket", "contact")
            .first()
        )

    async def _reply(self, conversation_id, text):
        conversation = await self._conversation_for(conversation_id)
        if conversation is None:
            return
        await database_sync_to_async(messaging.agent_message)(conversation, self.user, text)

    async def _typing(self, conversation_id):
        conversation = await self._conversation_for(conversation_id)
        if conversation is None:
            return
        await database_sync_to_async(messaging.broadcast_typing)(conversation, who="agent")

    @database_sync_to_async
    def _heartbeat(self):
        presence.heartbeat(self.user.pk)

    @database_sync_to_async
    def _go_online(self):
        from apps.chat.services import lifecycle

        presence.go_online(self.user.pk, capacity=lifecycle.default_capacity())

    @database_sync_to_async
    def _go_offline(self):
        """FR-014 makes this refusable while conversations are held; the check lands with the
        console in Phase 4, where the agent can actually see what is still open."""
        presence.go_offline(self.user.pk)
