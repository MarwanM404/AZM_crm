"""
The single customer-facing message filter (FR-014, FR-015; T132).

Every path that can reach a customer — templates, emails, exports, future APIs — MUST route
through `public_messages_for(ticket)` rather than querying `ticket.messages` directly.
tests/test_internal_visibility.py enumerates known customer-facing call sites and asserts
none of them can emit a message with visibility=INTERNAL.
"""

from apps.tickets.models import Message


def public_messages_for(ticket):
    """The only messages a customer may ever see for this ticket."""
    return ticket.messages.filter(visibility=Message.Visibility.PUBLIC).order_by("created_at")


def staff_messages_for(ticket):
    """All messages, public and internal, for staff-facing views only."""
    return ticket.messages.all().order_by("created_at")
