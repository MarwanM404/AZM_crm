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


def conversation_for(ticket):
    """What the customer may read, in order.

    Goes through `public_messages_for` rather than filtering here. That function is the one
    place this product's internal boundary is written down (MVP FR-014/FR-015), and the note
    at the top of apps/tickets/services/visibility.py asks callers never to inline the filter
    — because the safe query and the unsafe one differ by one clause and the unsafe one is
    shorter.
    """
    return public_messages_for(ticket).select_related("author")
