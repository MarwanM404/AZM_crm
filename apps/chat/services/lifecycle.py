"""
Starting and ending a conversation (FR-003, FR-009, FR-040).

The ticket is created with the conversation rather than at the end, so a transcript can never
be orphaned by an unexpected ending — a crash, a closed laptop, a customer who walks away.
The visitor is not shown the reference until the conversation ends, because the agent may
attach it to an existing ticket in between and a reference handed out early could be one the
customer can no longer use (FR-040, FR-041).
"""

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.chat.models import Conversation
from apps.chat.services import assignment, groups, messaging, presence, queue, tokens
from apps.tickets.models import Ticket


@transaction.atomic
def start(*, contact, department, branch, category, subject: str) -> tuple:
    """Create the ticket, the conversation and the visitor's token together.

    Returns (conversation, token). The token is returned rather than stored in readable form:
    only its hash goes to the database.
    """
    ticket = Ticket.objects.create(
        contact=contact,
        organization=contact.organization,
        subject=subject[:255] or _("Live chat"),
        description="",
        category=category,
        origin_channel=Ticket.Channel.CHAT,
        department=department,
        branch=branch,
    )
    conversation = Conversation.objects.create(
        ticket=ticket,
        contact=contact,
        visitor_token_hash="",
        department=department,
        branch=branch,
    )
    token = tokens.issue(conversation.pk)
    conversation.visitor_token_hash = tokens.fingerprint(token)
    conversation.save(update_fields=["visitor_token_hash"])
    return conversation, token


def try_assign(conversation, candidate_user_ids):
    """Assign an available agent, or queue the visitor. Returns the agent id or None."""
    agent_id = assignment.assign(conversation, candidate_user_ids)
    if agent_id is None:
        queue.join(str(conversation.pk), conversation.department_id, conversation.branch_id)
    return agent_id


def end(conversation, *, reason, ended_by=None, resolve: bool = False):
    """Close a conversation, write its transcript, and free the agent's slot.

    Idempotent: a visitor closing the tab as the agent clicks end must not produce two
    endings, and either path arriving second must not undo the first.
    """
    if conversation.state == Conversation.State.ENDED:
        return conversation

    assignment.release(conversation)
    queue.leave(str(conversation.pk), conversation.department_id, conversation.branch_id)

    conversation.state = Conversation.State.ENDED
    conversation.ended_at = timezone.now()
    conversation.ended_by = ended_by
    conversation.end_reason = reason
    conversation.save(update_fields=["state", "ended_at", "ended_by", "end_reason", "updated_at"])

    if resolve:
        from apps.tickets.services.lifecycle import InvalidTransition, apply_transition

        try:
            apply_transition(conversation.ticket, Ticket.Status.RESOLVED, actor=ended_by)
        except InvalidTransition:
            pass  # an unusual status is not a reason to fail closing the conversation

    messaging.broadcast_system(conversation, text=_("This conversation has ended."))
    _announce_ended(conversation)
    return conversation


def _announce_ended(conversation):
    """The reference is given now, and only now — by this point the ticket it lands on is
    settled (FR-040)."""
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    payload = {"type": "chat.ended", "reference": conversation.ticket.reference}
    for group in (groups.public_group(conversation.pk), groups.staff_group(conversation.pk)):
        async_to_sync(get_channel_layer().group_send)(group, payload)


def candidate_agents(department_id, branch_id):
    """Online agents in scope with room, longest-idle first is not needed — any free agent
    will do, and preferring one would need a fairness rule nobody has asked for."""
    from apps.accounts.models import User

    eligible = User.objects.filter(
        department_id=department_id,
        branch_id=branch_id,
        is_active=True,
        role__in=[User.Role.AGENT, User.Role.SUPERVISOR],
    ).values_list("pk", flat=True)
    return presence.agents_with_capacity(list(eligible))


def anyone_available(department_id, branch_id) -> bool:
    """FR-039: with nobody online, chat is not offered at all."""
    from apps.accounts.models import User

    eligible = User.objects.filter(
        department_id=department_id,
        branch_id=branch_id,
        is_active=True,
        role__in=[User.Role.AGENT, User.Role.SUPERVISOR],
    ).values_list("pk", flat=True)
    return presence.anyone_online(list(eligible))


def default_capacity() -> int:
    return getattr(settings, "CHAT_DEFAULT_AGENT_CAPACITY", 3)
