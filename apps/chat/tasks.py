"""
Periodic chat housekeeping.

FR-042 says nobody is left queued for a desk that has closed. The obvious trigger — an agent
pressing "go offline" — turns out to be the *rare* path, and reasoning about why is what this
task exists for.

When an agent ends a conversation, the longest-waiting visitor is connected to them
immediately, so an agent almost never reaches "holding nothing" while people are still
waiting. And FR-014 refuses to let them go offline while they hold anything. So the graceful
path mostly cannot strand anyone.

What actually strands people is the ungraceful one: the laptop that slept, the browser that
was closed, the machine that lost its network on the way home. Nothing fires an event for
those — the presence key simply stops being refreshed and expires (see presence.py). No event
means no handler, which means a sweep, which means this.
"""

from celery import shared_task


@shared_task
def close_deserted_desks() -> int:
    """Offer the request form to anyone waiting where no agent is online any more (FR-042).

    Returns the number of visitors moved, so the schedule can be observed rather than assumed.
    """
    from apps.accounts.models import Branch, Department
    from apps.chat.services import lifecycle, queue

    moved = 0
    for department_id in Department.objects.filter(is_active=True).values_list("pk", flat=True):
        for branch_id in Branch.objects.filter(is_active=True).values_list("pk", flat=True):
            if queue.waiting_count(department_id, branch_id) == 0:
                continue
            moved += len(lifecycle.desk_closed_if_empty(department_id, branch_id))
    return moved


@shared_task
def sweep_interrupted_conversations() -> dict:
    """Act on a party who has gone silent (FR-033, FR-034).

    A sweep because absence is the one state that cannot announce itself. Every other
    transition here is driven by an event — a message, a click, a socket closing cleanly — but
    a laptop that shut mid-sentence sends nothing at all. Something has to go and look.

    Presence itself is still not swept: the liveness key either exists or has expired, and the
    TTL is the grace period (apps/chat/services/liveness.py). This only decides what to do
    about an expiry that has already happened.
    """
    from apps.chat.models import Conversation
    from apps.chat.services import lifecycle, liveness

    ended = requeued = 0
    active = Conversation.objects.filter(state=Conversation.State.ACTIVE).select_related(
        "ticket", "contact", "assigned_to"
    )

    for conversation in active:
        if liveness.gone(conversation.pk, liveness.VISITOR):
            lifecycle.visitor_gone(conversation)
            ended += 1
        elif conversation.assigned_to_id and liveness.gone(conversation.pk, liveness.AGENT):
            lifecycle.agent_gone(conversation)
            requeued += 1

    return {"ended": ended, "requeued": requeued}


@shared_task
def sweep_idle_conversations() -> dict:
    """Warn, then close (FR-036).

    The requirement is specifically that the warning comes *before* the close, not with it. A
    customer who stepped away for coffee gets a chance to say "still here"; one who has gone
    gets closed rather than holding an agent's slot all afternoon.

    Idle is measured from `last_activity_at`, which deliberately does not count internal notes
    — a supervisor writing about a customer who left is not the customer being present. See
    apps/chat/services/messaging.py.
    """

    from django.conf import settings
    from django.utils import timezone
    from django.utils.translation import gettext as _

    from apps.chat.models import Conversation
    from apps.chat.services import lifecycle, messaging

    limit = getattr(settings, "CHAT_IDLE_LIMIT_SECONDS", 600)
    warn_after = getattr(settings, "CHAT_IDLE_WARNING_SECONDS", 480)
    now = timezone.now()

    warned = closed = 0
    active = Conversation.objects.filter(state=Conversation.State.ACTIVE).select_related(
        "ticket", "contact", "assigned_to"
    )

    for conversation in active:
        idle_for = (now - conversation.last_activity_at).total_seconds()

        if idle_for >= limit:
            messaging.broadcast_system(
                conversation,
                text=_("This conversation was closed after a period of inactivity."),
            )
            lifecycle.end(conversation, reason=Conversation.EndReason.IDLE_TIMEOUT)
            closed += 1
        elif idle_for >= warn_after and conversation.idle_warned_at is None:
            messaging.broadcast_system(
                conversation,
                text=_("This conversation will close soon if nobody replies."),
            )
            conversation.idle_warned_at = now
            conversation.save(update_fields=["idle_warned_at", "updated_at"])
            warned += 1

    return {"warned": warned, "closed": closed}
