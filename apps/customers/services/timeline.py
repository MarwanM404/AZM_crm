"""
The organization timeline (FR-019).

One reverse-chronological stream combining the tickets raised by every contact at an
organization with the notes held against it, optionally narrowed to a single contact.

Tickets and notes live in different tables with no common parent, so the merge happens in
Python. Each source is capped and ordered in the database first, so the work is bounded by
the page size rather than by the organization's whole history — an organization with 5,000
tickets costs the same as one with 50. The cap is deliberately the page size doubled, so a
page can be filled entirely from either source.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from apps.customers.models import Note
from apps.tickets.models import Ticket

PAGE_SIZE = 25


@dataclass(frozen=True)
class Entry:
    kind: str  # "ticket" | "note"
    at: datetime
    obj: Any


def timeline_for(organization, contact=None, limit: int = PAGE_SIZE):
    """Newest first. Pass `contact` to narrow to one person's activity."""
    fetch = limit * 2

    tickets = (
        Ticket.objects.filter(organization=organization)
        .select_related("contact", "category", "assigned_to")
        .order_by("-created_at")
    )
    if contact is not None:
        tickets = tickets.filter(contact=contact)

    entries = [Entry("ticket", t.created_at, t) for t in tickets[:fetch]]

    # A note is held against the organization, not a contact, so narrowing to one contact
    # excludes notes rather than guessing which of them were about that person.
    if contact is None:
        notes = (
            Note.objects.filter(organization=organization)
            .select_related("author")
            .order_by("-created_at")
        )
        entries += [Entry("note", n.created_at, n) for n in notes[:fetch]]

    entries.sort(key=lambda e: e.at, reverse=True)
    return entries[:limit]
