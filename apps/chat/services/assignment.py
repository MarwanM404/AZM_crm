"""
Assigning a conversation to an agent (FR-004, FR-012).

The same race as taking a ticket in the MVP — two visitors arriving at one free agent — with
an extra wrinkle: capacity lives in Redis and the assignment lives in PostgreSQL. The slot is
claimed first because that is the contended resource, and released again if the database write
fails, because an agent who silently leaks capacity stops receiving conversations for no
visible reason and nothing in the system complains.
"""

from django.db import transaction
from django.utils import timezone

from apps.chat.models import Conversation
from apps.chat.services import liveness, presence


def assign(conversation: Conversation, candidate_user_ids) -> int | None:
    """Attach the first online agent with room. Returns their id, or None when nobody is free.

    The conversation row is locked and re-read inside the transaction, so two simultaneous
    assignments cannot both see it unassigned — the same guarantee as taking a ticket.
    """
    for user_id in candidate_user_ids:
        if not presence.has_capacity(user_id):
            continue
        if not presence.claim_slot(user_id):
            continue  # someone took the last slot between the check and the claim

        try:
            with transaction.atomic():
                locked = Conversation.objects.select_for_update().get(pk=conversation.pk)
                if locked.assigned_to_id is not None:
                    presence.release_slot(user_id)
                    return None
                locked.assigned_to_id = user_id
                locked.state = Conversation.State.ACTIVE
                locked.assigned_at = timezone.now()
                locked.save(update_fields=["assigned_to", "state", "assigned_at", "updated_at"])
        except Exception:
            # The slot was claimed and the attach failed. Give it back, or this agent quietly
            # loses capacity for the lifetime of their session.
            presence.release_slot(user_id)
            raise

        # Seeded here, at the one place an assignment can succeed, so no caller can forget.
        # Without it the interruption sweep sees an agent who has never been "seen" on this
        # conversation and requeues it within the grace period — every conversation, forever.
        liveness.seen(conversation.pk, liveness.AGENT)

        conversation.refresh_from_db()
        return user_id

    return None


def release(conversation: Conversation) -> None:
    """Free the agent's slot when a conversation ends or is requeued."""
    if conversation.assigned_to_id:
        presence.release_slot(conversation.assigned_to_id)
