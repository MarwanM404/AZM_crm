"""
Recording and broadcasting chat messages (FR-006, FR-008).

Two rules shape everything here.

**Persist, then broadcast.** A message is written to PostgreSQL before it reaches any socket.
Broadcasting first would feel marginally faster and would lose exactly the messages sent in
the moments before a crash — the ones a dispute is most likely to be about. A lost *delivery*
is recoverable: the client refetches. A lost *transcript* is not.

**Render per group, not per socket.** The public group and the staff group receive different
HTML for the same message, rendered here, in synchronous code, before the broadcast. Consumers
forward what they are given and make no decisions about visibility — which is what keeps the
boundary in one place rather than in three consumers.
"""

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.template.loader import render_to_string
from django.utils import timezone

from apps.chat.services import groups
from apps.tickets.models import Message, Ticket


def _broadcast(group_name: str, payload: dict) -> None:
    async_to_sync(get_channel_layer().group_send)(group_name, payload)


def _render(template: str, message: Message, conversation) -> str:
    return render_to_string(template, {"message": message, "conversation": conversation})


def record_and_broadcast(conversation, *, body: str, author=None, direction, visibility):
    """Store a message, then push it to the groups entitled to see it.

    An INTERNAL message goes to the staff group **only**. The visitor's socket is not a member
    of that group, so this is not a filter that could be forgotten — there is no route.
    """
    body = (body or "").strip()
    if not body:
        return None

    message = Message.objects.create(
        ticket=conversation.ticket,
        author=author,
        direction=direction,
        visibility=visibility,
        channel=Ticket.Channel.CHAT,
        body=body,
        delivery_status=Message.DeliveryStatus.NOT_APPLICABLE,
    )

    # Internal notes are staff talking to staff, and deliberately do not count as activity.
    # FR-036 closes an idle conversation, and `last_activity_at` is what "idle" is measured
    # from: if a whisper refreshed it, a supervisor writing notes about a customer who left
    # twenty minutes ago would hold the conversation open indefinitely, and the agent would
    # keep a slot occupied for someone who is gone.
    if visibility != Message.Visibility.INTERNAL:
        conversation.last_activity_at = timezone.now()
        # A conversation that woke up has not been warned about *this* idle period. Leaving
        # the mark set would mean the next silence closed with no warning at all, which is
        # exactly what FR-036 forbids.
        conversation.idle_warned_at = None
        conversation.save(update_fields=["last_activity_at", "idle_warned_at", "updated_at"])

    if visibility == Message.Visibility.INTERNAL:
        html = _render("chat/partials/whisper.html", message, conversation)
        _broadcast(
            groups.staff_group(conversation.pk),
            {"type": "chat.message", "html": html},
        )
        _hold_if_the_agent_is_not_listening(conversation, message, html)
        return message

    html = _render("chat/partials/message.html", message, conversation)
    _broadcast(groups.public_group(conversation.pk), {"type": "chat.message", "html": html})
    _broadcast(groups.staff_group(conversation.pk), {"type": "chat.message", "html": html})
    return message


def _hold_if_the_agent_is_not_listening(conversation, message, html) -> None:
    """A broadcast to a group with no live member is simply lost (T099).

    The note is already on the ticket either way — this is about the agent seeing it in time
    for it to be coaching rather than a post-mortem. Held against the agent who is handling
    the conversation *now*; see apps/chat/services/pending.py for why the key names them.

    Takes the already-rendered staff HTML rather than re-rendering: the replayed note must be
    the one that was written, and a second render is a second chance to reach for the wrong
    template.
    """
    from apps.chat.services import pending, presence

    agent_id = conversation.assigned_to_id
    if agent_id is None or presence.has_socket(agent_id):
        return
    pending.hold(conversation.pk, agent_id, message_id=message.pk, html=html)


def visitor_message(conversation, body: str):
    """From the customer. No author: it was not written by a member of staff."""
    return record_and_broadcast(
        conversation,
        body=body,
        author=None,
        direction=Message.Direction.INBOUND,
        visibility=Message.Visibility.PUBLIC,
    )


def agent_message(conversation, agent, body: str):
    return record_and_broadcast(
        conversation,
        body=body,
        author=agent,
        direction=Message.Direction.OUTBOUND,
        visibility=Message.Visibility.PUBLIC,
    )


def whisper(conversation, supervisor, body: str):
    """A private note. Reaches the staff group and nowhere else (FR-025)."""
    return record_and_broadcast(
        conversation,
        body=body,
        author=supervisor,
        direction=Message.Direction.OUTBOUND,
        visibility=Message.Visibility.INTERNAL,
    )


def broadcast_typing(conversation, *, who: str) -> None:
    """Transient and never persisted — a typing indicator is not part of the transcript."""
    for group in (groups.public_group(conversation.pk), groups.staff_group(conversation.pk)):
        _broadcast(group, {"type": "chat.typing", "who": who})


def broadcast_system(conversation, *, text: str, staff_only: bool = False) -> None:
    """A state change either party should see: assigned, ended, reconnecting."""
    html = render_to_string("chat/partials/system.html", {"text": text})
    payload = {"type": "chat.system", "html": html}
    _broadcast(groups.staff_group(conversation.pk), payload)
    if not staff_only:
        _broadcast(groups.public_group(conversation.pk), payload)


def history_for_visitor(conversation) -> list[str]:
    """Everything the customer is entitled to see, rendered, oldest first (FR-032, FR-035).

    Read from the database rather than a buffer held in the process. A buffer is precisely
    what a crash loses, and surviving a crash is half of what this feature is for — the other
    half being a phone in a tunnel, which a buffer would survive but which is the easier case.

    Goes through `public_messages_for`, the same filter every other customer-facing output
    uses (MVP FR-015). This is a second path to the customer's screen, and a replay that read
    the staff view would deliver every private note at once.
    """
    from apps.tickets.services.visibility import public_messages_for

    return [
        _render("chat/partials/message.html", message, conversation)
        for message in public_messages_for(conversation.ticket)
    ]
