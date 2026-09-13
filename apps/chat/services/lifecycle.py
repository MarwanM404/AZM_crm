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
from apps.chat.services import (
    assignment,
    groups,
    messaging,
    presence,
    queue,
    tokens,
    unread,
)
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
    if conversation.assigned_to_id:
        # An ended conversation still showing unread is a badge nobody can clear.
        unread.forget(conversation.pk, [conversation.assigned_to_id])

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

    # The slot this conversation held is now free, so the longest-waiting visitor gets it.
    # Without this the queue only ever moves when a *new* conversation starts, which means a
    # visitor can sit behind an agent who has been idle for ten minutes.
    connect_next_waiting(conversation.department_id, conversation.branch_id)
    return conversation


def connect_next_waiting(department_id, branch_id):
    """Assign the longest-waiting visitor to a free agent, and update everyone behind them.

    Loops rather than pulling one: several slots can free at once — an agent ending three
    conversations, or coming back online — and leaving visitors queued behind capacity that
    already exists is the same failure as not having the queue move at all.
    """
    connected = []
    while True:
        candidates = candidate_agents(department_id, branch_id)
        if not candidates:
            break
        token, score = queue.peek(department_id, branch_id)
        if token is None:
            break

        conversation = (
            Conversation.objects.filter(pk=int(token), state=Conversation.State.WAITING)
            .select_related("ticket", "contact")
            .first()
        )
        if conversation is None:
            # Gone since they queued — ended, or already taken. Release their place so the
            # next iteration serves whoever is actually still waiting.
            queue.leave(token, department_id, branch_id)
            continue

        if assignment.assign(conversation, candidates) is None:
            # The capacity we saw was taken in between. They keep their place — they were
            # never removed — and there is nothing free to give, so stop.
            break

        queue.leave(token, department_id, branch_id)
        connected.append(conversation)

    queue.announce_positions(department_id, branch_id)
    return connected


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


def desk_closed_if_empty(department_id, branch_id):
    """Empty the queue when the last online agent goes offline (FR-042).

    Called after any agent leaves, and does nothing while anyone else is still online: one of
    two agents going home is not the desk closing.

    For the people waiting this is the cruellest failure in the queue if it is missed. They
    arrived while the desk was open and took their place honestly; without this they watch a
    position that is accurate and will never change again.
    """
    from django.urls import reverse

    if presence.anyone_online(list(_eligible_agent_ids(department_id, branch_id))):
        return []

    fallback = reverse("intake:form")
    stranded = []
    for token in queue.drain(department_id, branch_id):
        conversation = (
            Conversation.objects.filter(pk=int(token), state=Conversation.State.WAITING)
            .select_related("contact", "ticket")
            .first()
        )
        if conversation is None:
            continue

        queue.announce_desk_closed(
            token,
            fallback=fallback,
            carry=_carry_from(conversation),
        )
        end(conversation, reason=Conversation.EndReason.DESK_CLOSED)
        stranded.append(conversation)
    return stranded


def _carry_from(conversation) -> dict:
    """What they already told us, so the request form opens filled in."""
    email = conversation.contact.details.filter(kind="EMAIL").values_list("value", flat=True)
    return {
        "full_name": conversation.contact.full_name,
        "email": next(iter(email), ""),
        "subject": conversation.ticket.subject,
    }


def _eligible_agent_ids(department_id, branch_id):
    from apps.accounts.models import User

    return User.objects.filter(
        department_id=department_id,
        branch_id=branch_id,
        is_active=True,
        role__in=[User.Role.AGENT, User.Role.SUPERVISOR],
    ).values_list("pk", flat=True)
