"""
The internal/public boundary (FR-014, FR-015; T132).

Every path that can reach a customer — emails, pages, exports, the APIs and channels that
arrive after the MVP — MUST take its data from `customer_facing_context()`. Nothing that
renders for a customer should touch `ticket.messages` directly, because the safe query and
the unsafe one differ by a single filter that is easy to omit and impossible to notice.

The boundary is guarded in three places rather than trusted once:

1. Here, by construction: the customer-facing context cannot contain an internal message.
2. In `apps.messaging.tasks`, which refuses outright to send a non-public message.
3. In `tests/test_internal_visibility.py`, which renders every customer-facing template with
   an internal note present and asserts it never appears — and fails if a new customer-facing
   template is added without being listed.

This matters more than the MVP alone suggests: live chat arrives immediately after launch
with supervisor whisper, where the same boundary carries private staff commentary during a
live conversation with the customer watching.
"""

from apps.tickets.models import Message


def public_messages_for(ticket):
    """The only messages a customer may ever see for this ticket."""
    return ticket.messages.filter(visibility=Message.Visibility.PUBLIC).order_by("created_at")


def staff_messages_for(ticket):
    """All messages, public and internal. Staff-facing views only."""
    return ticket.messages.all().order_by("created_at")


def customer_facing_context(ticket, **extra):
    """Build the template context for anything a customer will read.

    Deliberately narrow: it exposes the ticket's reference and its public thread, and nothing
    else. A template that wants to quote history gets `public_messages` and therefore cannot
    reach an internal note even by mistake — which is the point, since the failure is silent
    and irreversible once the email has left.
    """
    context = {
        "reference": ticket.reference,
        "subject": ticket.subject,
        "public_messages": public_messages_for(ticket),
    }
    context.update(extra)
    return context


def contains_internal_content(rendered: str, ticket) -> bool:
    """True if any internal message body appears in already-rendered output.

    A last-line check for tests and for any future export path: it inspects the finished
    text rather than the query that produced it, so it catches a leak that got in some other
    way — string concatenation, a cached fragment, a serializer written in a hurry.
    """
    internal_bodies = ticket.messages.filter(visibility=Message.Visibility.INTERNAL).values_list(
        "body", flat=True
    )
    return any(body and body in rendered for body in internal_bodies)
