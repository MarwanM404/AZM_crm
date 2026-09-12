"""
T136: list and detail views must not issue a query per row.

These assert a property rather than a number: the same page is rendered at two data sizes
and the query count must be identical. A fixed budget ("under 12 queries") drifts and invites
bumping; "does not grow with the data" is the thing that actually keeps a page usable at the
50,000 tickets and 10,000 organizations SC-009 names, and it fails loudly the moment someone
adds an unprefetched lookup to a template.
"""

import pytest
from django.test import Client
from django.urls import reverse

from apps.customers.models import Organization
from apps.customers.services.matching import find_or_create_contact
from apps.tickets.models import Message, Ticket


def _make_tickets(count, *, organization, department, branch, category, agent, start=0):
    for i in range(start, start + count):
        contact, _ = find_or_create_contact(
            full_name=f"Person {i}",
            email=f"person{i}@example.com",
            department=department,
            branch=branch,
        )
        contact.organization = organization
        contact.save(update_fields=["organization"])
        ticket = Ticket.objects.create(
            contact=contact,
            organization=organization,
            subject=f"Subject {i}",
            description="...",
            category=category,
            origin_channel=Ticket.Channel.WEB_FORM,
            department=department,
            branch=branch,
            assigned_to=agent,
        )
        Message.objects.create(
            ticket=ticket,
            author=agent,
            direction=Message.Direction.OUTBOUND,
            visibility=Message.Visibility.PUBLIC,
            channel=ticket.origin_channel,
            body=f"Reply {i}",
        )


@pytest.fixture
def workload(db, department, branch, category, agent):
    organization = Organization.objects.create(
        name="Najd Trading", department=department, branch=branch
    )
    return {
        "organization": organization,
        "department": department,
        "branch": branch,
        "category": category,
        "agent": agent,
    }


def _queries_for(url, agent, django_assert_num_queries=None):
    client = Client()
    client.force_login(agent)
    from django.db import connection, reset_queries
    from django.test.utils import override_settings

    with override_settings(DEBUG=True):
        reset_queries()
        response = client.get(url)
        assert response.status_code == 200
        return len(connection.queries)


@pytest.mark.django_db
def test_queue_query_count_does_not_grow_with_ticket_count(workload):
    _make_tickets(5, **workload)
    small = _queries_for(reverse("tickets:queue"), workload["agent"])

    _make_tickets(20, start=5, **workload)
    large = _queries_for(reverse("tickets:queue"), workload["agent"])

    assert large == small, (
        f"The queue issued {large} queries for 25 tickets and {small} for 5 — a query per "
        "row. Add select_related/prefetch_related for whatever the template walks."
    )


@pytest.mark.django_db
def test_organization_timeline_does_not_grow_with_contact_count(workload):
    url = reverse("customers:detail", args=[workload["organization"].pk])

    _make_tickets(5, **workload)
    small = _queries_for(url, workload["agent"])

    _make_tickets(20, start=5, **workload)
    large = _queries_for(url, workload["agent"])

    assert large == small, (
        f"The organization timeline issued {large} queries for 25 contacts and {small} for "
        "5. The contact list in the sidebar walks contact.details for each one."
    )


@pytest.mark.django_db
def test_customer_list_does_not_grow_with_organization_count(workload):
    agent, department, branch = workload["agent"], workload["department"], workload["branch"]
    small = _queries_for(reverse("customers:list"), agent)

    for i in range(15):
        Organization.objects.create(name=f"Org {i}", department=department, branch=branch)
    large = _queries_for(reverse("customers:list"), agent)

    assert large == small, (
        f"The customer list issued {large} queries for 16 organizations and {small} for 1. "
        "Counting contacts and tickets per row in the template is a query per row; annotate "
        "the queryset instead."
    )


@pytest.mark.django_db
def test_ticket_detail_does_not_grow_with_thread_length(workload):
    _make_tickets(1, **workload)
    ticket = Ticket.objects.first()
    url = reverse("tickets:detail", args=[ticket.reference])
    small = _queries_for(url, workload["agent"])

    for i in range(20):
        Message.objects.create(
            ticket=ticket,
            author=workload["agent"],
            direction=Message.Direction.OUTBOUND,
            visibility=Message.Visibility.PUBLIC,
            channel=ticket.origin_channel,
            body=f"Message {i}",
        )
    large = _queries_for(url, workload["agent"])

    assert large == small, (
        f"Ticket detail issued {large} queries for a 21-message thread and {small} for one. "
        "The thread walks message.author for each entry."
    )


@pytest.mark.django_db
def test_unlinked_contacts_does_not_grow_with_contact_count(workload):
    department, branch, agent = workload["department"], workload["branch"], workload["agent"]
    for i in range(3):
        find_or_create_contact(
            full_name=f"Unlinked {i}",
            email=f"unlinked{i}@example.com",
            department=department,
            branch=branch,
        )
    small = _queries_for(reverse("customers:unlinked"), agent)

    for i in range(3, 20):
        find_or_create_contact(
            full_name=f"Unlinked {i}",
            email=f"unlinked{i}@example.com",
            department=department,
            branch=branch,
        )
    large = _queries_for(reverse("customers:unlinked"), agent)

    assert large == small


# --- correctness beside the budgets ---
#
# A query budget alone rewards deleting the feature: removing the counts from the template
# satisfies "queries do not grow with rows" by rendering nothing. These assert the optimized
# queries still produce the right answers.


@pytest.mark.django_db
def test_customer_list_counts_are_correct_after_optimization(workload):
    _make_tickets(3, **workload)
    empty = Organization.objects.create(
        name="Aaa Empty Co", department=workload["department"], branch=workload["branch"]
    )

    client = Client()
    client.force_login(workload["agent"])
    body = client.get(reverse("customers:list")).content.decode()

    rows = [row for row in body.split("table__row") if "Najd Trading" in row]
    assert rows, "the populated organization is missing from the list"
    assert "3" in rows[0], f"expected 3 contacts and 3 tickets in the row: {rows[0][:400]}"

    empty_rows = [row for row in body.split("table__row") if empty.name in row]
    assert empty_rows
    assert "0" in empty_rows[0]


@pytest.mark.django_db
def test_organization_sidebar_still_shows_contact_details_after_prefetch(workload):
    _make_tickets(2, **workload)

    client = Client()
    client.force_login(workload["agent"])
    body = client.get(
        reverse("customers:detail", args=[workload["organization"].pk])
    ).content.decode()

    assert "person0@example.com" in body
    assert "Person 0" in body
