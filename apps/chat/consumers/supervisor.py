"""
The supervisor's socket (FR-020 to FR-023).

**Joins the staff group only.** Group membership governs what this socket *receives*, so
this is what makes an observer see the staff view of the conversation — public messages and
internal notes alike — without receiving anything twice. It is worth being precise about what
it does not do: membership is not what stops a supervisor writing to the customer. Nothing is
sent from here at all. Every outbound message goes through `apps/chat/services/messaging.py`,
which chooses its groups explicitly, and no frame handler below calls it.

So an observer cannot reach the customer for two reasons, in this order: there is no code path
from this socket that writes a public message, and customer-directed frames are refused
outright rather than left unhandled. The customer's own socket joining the public group only
is what keeps internal notes away from *them* — that is the visitor consumer's guarantee, not
this one.

The customer is never told (FR-021). That is not implemented as a suppression of some
notification — there is simply no notification. Connecting here sends nothing to anybody,
which is why the invisibility tests assert that the visitor's socket receives *no frame of
any kind* rather than no message: silence is the implementation.

Watching is recorded (FR-023). An `Observation` row opens on connect and closes on
disconnect, because a supervisor reading a colleague's live conversation is an exercise of
authority over someone who cannot see them.
"""

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.accounts.models import User
from apps.chat.consumers.base import ChatConsumer, RateLimiter
from apps.chat.models import Conversation, Observation
from apps.chat.services import groups, messaging

OBSERVER_ROLES = {User.Role.SUPERVISOR, User.Role.ADMINISTRATOR}

# Frames that would reach the customer. Rejected explicitly rather than left unhandled: an
# unhandled frame is silence, which looks exactly like a bug and tells the supervisor nothing.
# A rejection is a decision, and it says why (FR-022).
CUSTOMER_DIRECTED = {"message", "typing", "close"}


class SupervisorConsumer(ChatConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated or user.role not in OBSERVER_ROLES:
            await self.close()
            return

        self.user = user
        self.conversation = await self._authorize(self._conversation_id_from_scope())
        if self.conversation is None:
            # Out of scope and never existed are refused identically. A refusal that
            # distinguished them would let a supervisor enumerate other departments (FR-043).
            await self.close()
            return

        self.limiter = RateLimiter(capacity=20, refill_per_second=4.0)
        self.observation_id = await self._open_observation()

        # The staff group, and only the staff group.
        await self.channel_layer.group_add(
            groups.staff_group(self.conversation.pk), self.channel_name
        )
        await self.accept()
        await self._announce_to_agent()

    @database_sync_to_async
    def _announce_to_agent(self):
        """Tell the agent, in their own thread, that someone is watching.

        FR-021 settles the customer: never told. The spec is silent about the agent, so this
        is a decision. The desk's position is that the `Observation` record satisfies the
        audit requirement, and the agent is additionally told live — an agent who later
        discovers that colleagues watch silently has reason to distrust the whole system,
        and the cost of that outlasts any one observed conversation.

        The observer is named rather than described. "A supervisor is watching" invites the
        agent to guess which one, and guessing wrong is worse than knowing.

        `staff_only=True` is not optional: without it this notice goes to the customer's
        socket and breaks FR-021 outright. apps/chat/tests/test_observation_invisible.py
        fails if it is ever dropped.
        """
        messaging.broadcast_system(
            self.conversation,
            text=_(
                "%(observer)s is observing this conversation. They can send you private "
                "notes that the customer cannot see."
            )
            % {"observer": self.user.full_name},
            staff_only=True,
        )

    @database_sync_to_async
    def _announce_departure(self):
        """And tell them when it stops.

        Not a nicety: a "someone is watching" notice that never clears is worse than no
        notice, because the agent goes on believing it after it stopped being true.
        """
        messaging.broadcast_system(
            self.conversation,
            text=_("%(observer)s is no longer observing.") % {"observer": self.user.full_name},
            staff_only=True,
        )

    async def disconnect(self, code):
        conversation = getattr(self, "conversation", None)
        if conversation is not None:
            # Announce before leaving the group: afterwards this socket is no longer a member,
            # but the agent's socket still is, so the notice reaches them either way — the
            # ordering matters only for what this observer sees of their own departure.
            await self._announce_departure()
            await self.channel_layer.group_discard(
                groups.staff_group(conversation.pk), self.channel_name
            )
        if getattr(self, "observation_id", None) is not None:
            await self._close_observation()

    async def receive(self, text_data=None, bytes_data=None):
        payload = self.parse(text_data)
        kind = payload.get("type")

        if not self.limiter.allow():
            await self.send_event(type="throttled")
            return

        if kind in CUSTOMER_DIRECTED:
            await self.send_event(
                type="refused",
                reason=_("Observing a conversation does not let you take part in it."),
            )
            return

    # --- database work, behind the async boundary ---

    def _conversation_id_from_scope(self):
        query = parse_qs((self.scope.get("query_string") or b"").decode())
        raw = (query.get("conversation") or [""])[0]
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    @database_sync_to_async
    def _authorize(self, conversation_id):
        """Scoped by the same manager every other lookup uses, so "not yours" and "not there"
        produce the same `None` without this function having to think about it."""
        if conversation_id is None:
            return None
        return (
            Conversation.objects.for_user(self.user)
            .filter(pk=conversation_id)
            .select_related("ticket", "contact", "assigned_to")
            .first()
        )

    @database_sync_to_async
    def _open_observation(self):
        return Observation.objects.create(conversation=self.conversation, observer=self.user).pk

    @database_sync_to_async
    def _close_observation(self):
        Observation.objects.filter(pk=self.observation_id, ended_at__isnull=True).update(
            ended_at=timezone.now()
        )
