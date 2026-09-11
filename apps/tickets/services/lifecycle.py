"""
Ticket status lifecycle (FR-009).

The permitted edges live on Ticket.ALLOWED_TRANSITIONS; this module is the only place that
applies one, so the guard cannot be bypassed by a view that forgets to check. Every applied
transition is saved with the side effects the status implies (resolved_at set on resolve,
cleared on reopen), which keeps the SLA phase's future reporting honest.

The lifecycle itself is an assumption pending stakeholder confirmation (T147).
"""

from django.utils import timezone

from apps.tickets.models import Ticket


class InvalidTransition(Exception):
    """Raised when a caller asks for an edge the lifecycle does not permit."""

    def __init__(self, current, requested):
        self.current = current
        self.requested = requested
        super().__init__(f"Cannot move a ticket from {current} to {requested}")


def apply_transition(ticket: Ticket, new_status: str, *, actor) -> Ticket:
    if new_status == ticket.status:
        return ticket
    if not ticket.can_transition_to(new_status):
        raise InvalidTransition(ticket.status, new_status)

    fields = ["status"]
    ticket.status = new_status

    if new_status == Ticket.Status.RESOLVED:
        ticket.resolved_at = timezone.now()
        fields.append("resolved_at")
    elif ticket.resolved_at is not None:
        # Reopened: the previous resolution no longer stands, so the stamp must not linger.
        ticket.resolved_at = None
        fields.append("resolved_at")

    ticket.save(update_fields=fields)
    return ticket


def reopen_for_customer_reply(ticket: Ticket) -> Ticket:
    """An inbound customer message must never be lost behind a finished ticket (spec edge
    case). Resolved and closed tickets return to OPEN; a ticket awaiting the customer is ours
    again the moment they answer."""
    if ticket.status in (
        Ticket.Status.RESOLVED,
        Ticket.Status.CLOSED,
        Ticket.Status.PENDING_CUSTOMER,
    ):
        return apply_transition(ticket, Ticket.Status.OPEN, actor=None)
    return ticket
