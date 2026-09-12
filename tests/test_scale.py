"""
SC-009: the queue and the organization timeline stay responsive at 50,000 tickets and
10,000 organizations.

Timing assertions in a test suite are a trap — they fail on a busy machine and get muted. So
these assert the two properties that actually determine whether the pages survive the volume,
and which hold regardless of hardware:

1. The work is bounded. A page renders a fixed number of rows no matter how many exist, and
   issues the same number of queries at any size.
2. The filters are indexed. The queue's ordering and filtering columns are covered by an
   index, so the database is not sorting the whole table to show twenty-five rows.

Marked `slow`: run with `-m "not slow"` for a fast loop.
"""

import pytest
from django.db import connection
from django.test import Client
from django.urls import reverse

from apps.customers.models import Contact, ContactDetail, Organization
from apps.tickets.models import Ticket

pytestmark = pytest.mark.django_db


def _bulk_tickets(count, *, department, branch, category, contact, organization=None):
    """Created in bulk deliberately: the point is volume, not the per-ticket side effects,
    and 5,000 saved one at a time would make this test unusably slow."""
    year = 2026
    tickets = [
        Ticket(
            reference=f"AZM-{year}-{900000 + i:06d}",
            contact=contact,
            organization=organization,
            subject=f"Bulk subject {i}",
            description="...",
            category=category,
            priority=Ticket.Priority.NORMAL if i % 3 else Ticket.Priority.URGENT,
            status=Ticket.Status.OPEN if i % 2 else Ticket.Status.NEW,
            origin_channel=Ticket.Channel.WEB_FORM,
            department=department,
            branch=branch,
        )
        for i in range(count)
    ]
    Ticket.objects.bulk_create(tickets, batch_size=500)


@pytest.mark.slow
def test_queue_renders_a_bounded_page_at_volume(department, branch, category, contact, agent):
    _bulk_tickets(5000, department=department, branch=branch, category=category, contact=contact)
    assert Ticket.objects.count() >= 5000

    client = Client()
    client.force_login(agent)

    from django.db import reset_queries
    from django.test.utils import override_settings

    with override_settings(DEBUG=True):
        reset_queries()
        response = client.get(reverse("tickets:queue"))
        queries = len(connection.queries)

    assert response.status_code == 200
    body = response.content.decode()

    # Bounded output: the page shows a page of rows, not five thousand.
    rendered_rows = body.count('class="table__row"')
    assert rendered_rows <= 30, f"the queue rendered {rendered_rows} rows"
    assert queries < 15, f"the queue issued {queries} queries at volume"


@pytest.mark.slow
def test_queue_query_count_is_the_same_at_5k_as_at_50(department, branch, category, contact, agent):
    client = Client()
    client.force_login(agent)
    url = reverse("tickets:queue")

    from django.db import reset_queries
    from django.test.utils import override_settings

    def count():
        with override_settings(DEBUG=True):
            reset_queries()
            client.get(url)
            return len(connection.queries)

    _bulk_tickets(50, department=department, branch=branch, category=category, contact=contact)
    small = count()

    Ticket.objects.all().delete()
    _bulk_tickets(5000, department=department, branch=branch, category=category, contact=contact)
    large = count()

    assert large == small, f"{large} queries at 5,000 tickets vs {small} at 50"


def test_the_queue_ordering_columns_are_indexed():
    """Without this index the database sorts the whole table to produce twenty-five rows —
    invisible at test-data size and ruinous at SC-009's volume."""
    indexes = [idx for idx in Ticket._meta.indexes]
    covered = [tuple(idx.fields) for idx in indexes]
    assert any(
        fields[:2] == ("department", "branch") and "status" in fields and "priority" in fields
        for fields in covered
    ), f"no index covers the queue's scope-and-filter columns: {covered}"


def test_soft_delete_uniqueness_is_a_partial_index():
    """A plain unique constraint would let one deleted record block its own email address
    forever; the partial index is what keeps the address reusable (FR-020)."""
    constraints = {c.name: c for c in ContactDetail._meta.constraints}
    partial = constraints.get("unique_contact_detail_when_not_deleted")
    assert partial is not None
    assert partial.condition is not None, "the uniqueness constraint is not conditional"


@pytest.mark.slow
def test_organization_timeline_is_bounded_by_page_size(department, branch, category, agent):
    organization = Organization.objects.create(
        name="Large Co", department=department, branch=branch
    )
    contact = Contact.objects.create(
        full_name="Bulk Contact",
        organization=organization,
        department=department,
        branch=branch,
    )
    _bulk_tickets(
        2000,
        department=department,
        branch=branch,
        category=category,
        contact=contact,
        organization=organization,
    )

    from apps.customers.services.timeline import PAGE_SIZE, timeline_for

    entries = timeline_for(organization)
    assert len(entries) <= PAGE_SIZE
