"""
Linking a contact to an organization (FR-041, FR-042).

The distinction this module exists to hold:

- A ticket raised while the contact had NO organization has no history to protect. Filling
  it in is a correction, and the ticket joins the organization's timeline.
- A ticket raised UNDER an organization did happen under that organization. Moving the
  contact elsewhere later must not rewrite it, or the record stops being true.

So the backfill is narrowed to tickets whose organization is null. Nothing ever overwrites a
non-null one.
"""

from django.db import transaction

from apps.tickets.models import Ticket


@transaction.atomic
def link_contact(contact, organization):
    """Attach `contact` to `organization` and backfill only its unattributed tickets.
    Returns the number of tickets corrected."""
    contact.organization = organization
    contact.save(update_fields=["organization"])

    return Ticket.objects.filter(contact=contact, organization__isnull=True).update(
        organization=organization
    )
