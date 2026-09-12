"""
The conversation as a permanent record (FR-040, FR-041, T071).

There is no "write the transcript" step at the end of a conversation, and that is deliberate.
Messages are written to the ticket as they are sent (see `messaging.record_and_broadcast`), so
a conversation that ends by a crash, a closed laptop or a customer who simply walks away still
has everything that was said up to that moment. SC-003 asks for 100% transcript completeness
*including* conversations ended by a disconnection, and no end-of-conversation flush can
deliver that — it can only ever capture the endings that were polite enough to happen.

What is left for this module, then, is not writing the transcript but **moving** it: the agent
recognising that the customer already has an open ticket about this problem, and re-pointing
the conversation onto it.
"""

from django.db import transaction
from django.utils.translation import gettext as _
from django.utils.translation import ngettext

from apps.chat.models import Conversation
from apps.tickets.models import Message, Ticket


class NotAttachable(Exception):
    """The target ticket exists and is in scope, but may not receive this transcript."""


def can_attach_to(conversation, ticket) -> bool:
    """Whether `conversation`'s transcript may be moved onto `ticket`.

    Scope has already been enforced by the caller: `ticket` is in the agent's department and
    branch, and is not deleted, and `move_to` has already handled the case where `ticket` is
    the conversation's own placeholder. What is left is the *policy* question.

    Return True to allow the move, False to refuse it (the endpoint answers 422).

    The rule is deliberately the strict one. Attaching is not reversible through the UI — the
    placeholder is retired and the messages are gone from it — so the cost of a wrong refusal
    (the agent fixes the contact, or reopens the ticket, and tries again) is much lower than
    the cost of a wrong acceptance (one customer's words sitting in another's history, or two
    live transcripts interleaved in a single ticket with no way to tell them apart).
    """
    # One customer's words must not land in another customer's history. A mis-identified
    # contact is a real situation, but the fix for it is to correct the contact, not to
    # merge the records.
    if ticket.contact_id != conversation.contact_id:
        return False

    # A settled ticket that quietly grows a new transcript makes "resolved" mean nothing, and
    # the resolution timestamp already recorded on it becomes a lie. Reopening is a
    # deliberate act with its own audit entry; it should stay deliberate.
    if ticket.status in {Ticket.Status.RESOLVED, Ticket.Status.CLOSED}:
        return False

    # Two live conversations writing into one ticket interleaves two transcripts by timestamp
    # with nothing marking where one ends and the other begins.
    if (
        Conversation.objects.filter(ticket=ticket)
        .exclude(pk=conversation.pk)
        .exclude(state=Conversation.State.ENDED)
        .exists()
    ):
        return False

    return True


@transaction.atomic
def move_to(conversation, target: Ticket, *, actor) -> Ticket:
    """Re-point the conversation and its transcript onto `target`, retiring the placeholder.

    Attaching is a re-point, not a copy. The messages already exist as rows on the placeholder
    ticket, so moving them is an UPDATE of one foreign key — no duplication, no window in
    which a message exists twice or not at all.
    """
    placeholder = conversation.ticket
    if placeholder.pk == target.pk:
        return target  # a double-clicked button must not delete the ticket it just attached to

    if not can_attach_to(conversation, target):
        raise NotAttachable

    moved = Message.objects.filter(ticket=placeholder).update(ticket=target)

    conversation.ticket = target
    conversation.save(update_fields=["ticket", "updated_at"])

    # Both sides are audited. A ticket that grows a transcript and a ticket that disappears
    # are the same event seen from two ends; recording one without the other leaves the
    # history unreconstructable. auditlog records the diff, so touching a field is what
    # produces the entry — the description carries the human-readable reason.
    target.description = _append_note(
        target.description,
        # ngettext, not a bare %d: Arabic has six plural forms and "1 رسائل" is wrong in a
        # way an English speaker reading the catalog would never notice.
        ngettext(
            "Live chat %(reference)s attached (%(count)d message).",
            "Live chat %(reference)s attached (%(count)d messages).",
            moved,
        )
        % {"reference": placeholder.reference, "count": moved},
    )
    target.save(update_fields=["description", "updated_at"])

    placeholder.description = _append_note(
        placeholder.description,
        _("Transcript moved to %(reference)s.") % {"reference": target.reference},
    )
    placeholder.save(update_fields=["description", "updated_at"])
    placeholder.soft_delete(by=actor)

    return target


def _append_note(description: str, note: str) -> str:
    return f"{description}\n\n{note}".strip() if description else note
