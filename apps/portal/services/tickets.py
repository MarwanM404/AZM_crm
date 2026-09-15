"""
Reading a customer's own requests (T051).

One rule, stated once, so that no view has to remember it: a customer's requests are the ones
raised from the ADDRESS they confirmed. Not their organization's. Not a record linked to their
account at registration, because nothing is linked to their account at all.

Two natural implementations are wrong and both are shorter than the right one:

  * filter by `ticket.organization`, which is a field sitting right there on the model and
    which would show a junior employee every complaint their colleagues have ever made;
  * store a `Contact` on the account at registration, which fixes the association at the one
    moment we know least — before the customer has written in, and before anyone has checked
    that the address is theirs.

Matching by address at read time is what makes the awkward cases behave: an account with no
contact yet sees an empty list, an address recorded on two contacts sees both histories, and
an address edited by an administrator takes the view with it.
"""

from apps.customers.models import ContactDetail
from apps.tickets.models import Ticket
from apps.tickets.services.visibility import public_messages_for


def contact_ids_for(account):
    """Every contact record carrying this account's confirmed address.

    `ContactDetail.objects` excludes soft-deleted rows, so a detail staff have removed stops
    matching — which is the same answer staff see, and the portal must not be a second view
    of the data with different rules.

    Addresses are stored lowercased by `ContactDetail.save`, and `CustomerAccount.save`
    lowercases too, so this compares like with like without `iexact` — which would defeat the
    index on a table that grows with every customer.
    """
    return ContactDetail.objects.filter(
        kind=ContactDetail.Kind.EMAIL, value=account.email
    ).values_list("contact_id", flat=True)


def requests_for(account):
    """The customer's requests, newest activity first.

    Ordered explicitly. An unordered queryset comes back in whatever order the database finds
    convenient, which is stable on a small table, changes under load, and reads as a bug.

    `select_related` on category and assignee is not for display — neither is shown — but the
    list template touches nothing else, and the pair is here so that adding a column later
    does not silently turn this into a query per row. tests/test_query_budget.py is what
    would notice.
    """
    return (
        Ticket.objects.filter(contact_id__in=contact_ids_for(account))
        .select_related("contact")
        .order_by("-created_at")
    )


def request_for(account, reference):
    """One request of theirs, or None.

    Returns None rather than raising, so the caller decides the refusal — and the caller must
    answer 404 for "not yours" and for "never existed" alike (FR-017). A 403 here would
    confirm the reference exists, and a handful of those is a map of the desk's volume.
    """
    return requests_for(account).filter(reference=reference).first()


def page_for(ticket, form=None):
    """The whole template context for one request — built WITHOUT putting the ticket in it.

    `customer_facing_context` is this product's narrow context for anything a customer reads
    (MVP FR-014/FR-015), and its narrowness is the mechanism: a template that never receives
    the ticket cannot walk `ticket.messages.all` to an internal note, however carelessly it is
    edited later. `tests/test_internal_visibility.py` asserts that context contains no
    "ticket" key at all.

    The portal's detail screen was first written passing the ticket directly and filtering
    the messages instead. Every test passed, including the boundary ones — because the
    template as written did not reach for `ticket.messages`. The next person to edit it would
    have had a ticket object in scope and no reason to suspect it. The sweep found it, from
    the other end: it renders every customer-facing template with this narrow context, and
    the template failed because it wanted something the narrow context does not give.

    `description` is added because it is the customer's own opening words. It is their text;
    showing it to them discloses nothing.
    """
    from apps.portal.forms import ReplyForm
    from apps.tickets.services.visibility import customer_facing_context

    return customer_facing_context(
        ticket,
        description=ticket.description,
        status=ticket.get_status_display(),
        status_code=ticket.status.lower(),
        opened_at=ticket.created_at,
        updated_at=ticket.updated_at,
        public_messages=conversation_for(ticket),
        form=form or ReplyForm(),
    )


def conversation_for(ticket):
    """What the customer may read, in order.

    Goes through `public_messages_for` rather than filtering here. That function is the one
    place this product's internal boundary is written down (MVP FR-014/FR-015), and the note
    at the top of apps/tickets/services/visibility.py asks callers never to inline the filter
    — because the safe query and the unsafe one differ by one clause and the unsafe one is
    shorter.
    """
    return public_messages_for(ticket).select_related("author")


def reply_to(account, reference, body):
    """Add a customer's reply to one of their own requests. Returns the message, or None if
    the reference is not theirs.

    Two things are deliberately NOT decided here.

    What the reply does to the ticket's state is `reopen_for_customer_reply`'s decision — the
    same function the inbound email path calls. A copy of that rule would pass every test on
    the day it was written and would drift the first time somebody changed one of the two,
    and the symptom is a customer whose emailed reply reopens their ticket and whose portal
    reply does not. `test_the_portal_does_not_reimplement_the_state_rule` is a source check
    against exactly that, because a faithful copy passes behaviour tests.

    Whether the body is acceptable is the form's decision, made before this is called.
    Validating again here would be a second answer to "how long is too long".

    The whole thing is one transaction: a reply that reopened a ticket and then failed to
    record itself would leave an agent looking at a request that has apparently reopened for
    no reason.
    """
    from django.db import transaction

    from apps.tickets.models import Message
    from apps.tickets.services.lifecycle import reopen_for_customer_reply

    ticket = request_for(account, reference)
    if ticket is None:
        return None

    with transaction.atomic():
        reopen_for_customer_reply(ticket)
        return Message.objects.create(
            ticket=ticket,
            # Null, exactly as an emailed reply is. `author` means the STAFF author, and a
            # customer is not a User — putting anything here would make the audit trail claim
            # an agent wrote what a customer wrote.
            author=None,
            direction=Message.Direction.INBOUND,
            visibility=Message.Visibility.PUBLIC,
            channel=Ticket.Channel.PORTAL,
            body=body,
            delivery_status=Message.DeliveryStatus.NOT_APPLICABLE,
        )


def raise_request(account, category, subject, description, language):
    """Open a request on behalf of a signed-in customer (FR-023). Returns the ticket.

    Calls the same `open_ticket` the public form calls, rather than creating the ticket here
    — FR-025 requires the anonymous form to keep behaving exactly as it does, and the way to
    get that is for the two paths to be one path. A portal copy would agree with it today and
    diverge the first time either was touched, and the people who would notice the anonymous
    one breaking are strangers with no account and no way to report it beyond giving up.

    The address is the account's confirmed one and is never taken from the request. A view
    that read an address out of the form would let a signed-in customer file against somebody
    else's contact record, on a screen that looked exactly the same.

    The name for a customer with no contact record yet is the local part of their address —
    the same thing `apps/messaging/services/inbound.py` does for an unknown sender. Asking a
    signed-in customer for their name is what FR-023 forbids, and a placeholder would put
    "Unknown" in the customer list for a real person.
    """
    from apps.intake.services.creation import open_ticket

    ticket, _contact, _created = open_ticket(
        full_name=account.email.split("@")[0],
        email=account.email,
        subject=subject,
        description=description,
        category=category,
        channel=Ticket.Channel.PORTAL,
        language=language,
    )
    return ticket
