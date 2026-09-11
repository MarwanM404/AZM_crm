"""FR-003: unique, stable ticket references, format AZM-{year}-{sequence}."""

import re

import pytest

from apps.tickets.models import Ticket

REFERENCE_RE = re.compile(r"^AZM-\d{4}-\d{6}$")


@pytest.mark.django_db
def test_ticket_reference_matches_format(department, branch, category):
    from apps.customers.services.matching import find_or_create_contact

    contact, _ = find_or_create_contact(
        full_name="Jane", email="jane@example.com", department=department, branch=branch
    )
    ticket = Ticket.objects.create(
        contact=contact,
        subject="Help",
        description="Something broke",
        category=category,
        origin_channel=Ticket.Channel.WEB_FORM,
        department=department,
        branch=branch,
    )
    assert REFERENCE_RE.match(ticket.reference), ticket.reference


@pytest.mark.django_db
def test_ticket_references_are_unique_and_sequential(department, branch, category):
    from apps.customers.services.matching import find_or_create_contact

    contact, _ = find_or_create_contact(
        full_name="Jane", email="jane@example.com", department=department, branch=branch
    )
    tickets = [
        Ticket.objects.create(
            contact=contact,
            subject=f"Issue {i}",
            description="...",
            category=category,
            origin_channel=Ticket.Channel.WEB_FORM,
            department=department,
            branch=branch,
        )
        for i in range(3)
    ]
    references = [t.reference for t in tickets]
    assert len(set(references)) == 3
    sequences = [int(r.rsplit("-", 1)[1]) for r in references]
    assert sequences == sorted(sequences)


@pytest.mark.django_db
def test_reference_never_changes_once_assigned(department, branch, category):
    from apps.customers.services.matching import find_or_create_contact

    contact, _ = find_or_create_contact(
        full_name="Jane", email="jane@example.com", department=department, branch=branch
    )
    ticket = Ticket.objects.create(
        contact=contact,
        subject="Help",
        description="...",
        category=category,
        origin_channel=Ticket.Channel.WEB_FORM,
        department=department,
        branch=branch,
    )
    original = ticket.reference
    ticket.subject = "Updated subject"
    ticket.save()
    ticket.refresh_from_db()
    assert ticket.reference == original
