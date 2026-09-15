"""
T136: list and detail views must not issue a query per row.

These assert a property rather than a number: the same page is rendered at two data sizes
and the query count must be identical. A fixed budget ("under 12 queries") drifts and invites
bumping; "does not grow with the data" is the thing that actually keeps a page usable at the
50,000 tickets and 10,000 organizations SC-009 names, and it fails loudly the moment someone
adds an unprefetched lookup to a template.
"""

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.customers.models import Organization
from apps.customers.services.matching import find_or_create_contact
from apps.tickets.models import Message, Ticket


@pytest.fixture
def customer_client_for_budget(db):
    """A signed-in portal customer. Local to this file so the portal's own conftest fixtures
    do not have to be importable from tests/."""
    from django.conf import settings

    from apps.portal.auth import CUSTOMER_SESSION_KEY
    from apps.portal.models import CustomerAccount

    account = CustomerAccount.objects.create_account(
        email="budget@example.com", password="a-long-enough-passphrase-42"
    )
    account.confirm()

    client = Client()
    session = client.session
    session[CUSTOMER_SESSION_KEY] = account.pk
    session.save()
    client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key
    return client, account


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


# --- live chat (T125) ---
#
# The console shows several conversations at once, each with its own customer context, which
# is exactly the shape that grows a query per row. The property asserted is the same as above:
# not a fixed budget, but that the count is identical at one conversation and at several.


def _make_conversations(count, *, department, branch, category, agent):
    from django.utils import timezone

    from apps.chat.models import Conversation
    from apps.customers.models import Organization
    from apps.tickets.models import Message, Ticket

    organization = Organization.objects.create(
        name="Chatty Co", department=department, branch=branch
    )
    made = []
    for i in range(count):
        contact, _ = find_or_create_contact(
            full_name=f"Chatter {i}",
            email=f"chatter{i}@example.com",
            department=department,
            branch=branch,
        )
        contact.organization = organization
        contact.save(update_fields=["organization"])
        ticket = Ticket.objects.create(
            contact=contact,
            organization=organization,
            subject=f"Chat {i}",
            description="",
            category=category,
            origin_channel=Ticket.Channel.CHAT,
            department=department,
            branch=branch,
        )
        Message.objects.create(
            ticket=ticket,
            author=None,
            direction=Message.Direction.INBOUND,
            visibility=Message.Visibility.PUBLIC,
            channel=Ticket.Channel.CHAT,
            body=f"Hello {i}",
        )
        made.append(
            Conversation.objects.create(
                ticket=ticket,
                contact=contact,
                visitor_token_hash=f"hash-{i}",
                department=department,
                branch=branch,
                assigned_to=agent,
                state=Conversation.State.ACTIVE,
                assigned_at=timezone.now(),
            )
        )
    return made


@pytest.mark.django_db
def test_the_console_does_not_query_per_conversation(
    agent, department, branch, category, django_assert_num_queries
):
    """An agent holding three conversations is the ordinary case, and each one carries a
    contact, an organization and contact details beside it — a query per row here is three
    round trips on every page load, growing with how busy the agent is."""
    from apps.chat.services.redis_client import reset_for_tests

    reset_for_tests()
    client = Client()
    client.force_login(agent)

    _make_conversations(1, department=department, branch=branch, category=category, agent=agent)
    with CaptureQueriesContext(connection) as few:
        client.get(reverse("chat:console"))

    _make_conversations(4, department=department, branch=branch, category=category, agent=agent)
    with CaptureQueriesContext(connection) as many:
        client.get(reverse("chat:console"))

    assert len(many) == len(few), (
        f"The console issued {len(few)} queries for one conversation and {len(many)} for "
        "five. Something in chat/console.html or its partials reads through a relation that "
        "is not prefetched."
    )
    reset_for_tests()


@pytest.mark.django_db
def test_the_conversation_view_does_not_query_per_message(
    agent, department, branch, category, django_assert_num_queries
):
    """A long conversation is the normal end state of a short one."""
    from apps.chat.services.redis_client import reset_for_tests
    from apps.tickets.models import Message, Ticket

    reset_for_tests()
    client = Client()
    client.force_login(agent)
    conversation = _make_conversations(
        1, department=department, branch=branch, category=category, agent=agent
    )[0]

    with CaptureQueriesContext(connection) as few:
        client.get(reverse("chat:conversation", args=[conversation.pk]))

    for i in range(20):
        Message.objects.create(
            ticket=conversation.ticket,
            author=agent,
            direction=Message.Direction.OUTBOUND,
            visibility=Message.Visibility.PUBLIC,
            channel=Ticket.Channel.CHAT,
            body=f"Reply {i}",
        )

    with CaptureQueriesContext(connection) as many:
        client.get(reverse("chat:conversation", args=[conversation.pk]))

    assert len(many) == len(few), (
        f"The conversation view issued {len(few)} queries with one message and {len(many)} "
        "with twenty-one. The author lookup in chat/partials/message.html is the usual cause."
    )
    reset_for_tests()


@pytest.mark.django_db
def test_the_supervision_list_does_not_query_per_conversation(
    supervisor, department, branch, category, agent, django_assert_num_queries
):
    from apps.chat.services.redis_client import reset_for_tests

    reset_for_tests()
    client = Client()
    client.force_login(supervisor)

    _make_conversations(1, department=department, branch=branch, category=category, agent=agent)
    with CaptureQueriesContext(connection) as few:
        client.get(reverse("chat:supervise"))

    _make_conversations(4, department=department, branch=branch, category=category, agent=agent)
    with CaptureQueriesContext(connection) as many:
        client.get(reverse("chat:supervise"))

    assert len(many) == len(few)
    reset_for_tests()


# --- the customer portal (spec 004, T050) ---


@pytest.mark.django_db
def test_the_portal_request_list_does_not_query_per_request(
    customer_client_for_budget, department, branch, category
):
    """The portal's list is the page most likely to be opened by somebody on a phone on a bad
    connection, and the one whose owner cannot ask an administrator to make it faster.

    Asserted as "the count does not change with the number of rows" rather than as a budget,
    for the reason at the top of this file.
    """
    from apps.customers.models import Contact, ContactDetail
    from apps.tickets.models import Ticket

    client, account = customer_client_for_budget
    contact = Contact.objects.create(
        full_name="Noura Al-Harbi", department=department, branch=branch
    )
    ContactDetail.objects.create(
        contact=contact,
        kind=ContactDetail.Kind.EMAIL,
        value=account.email,
        department=department,
        branch=branch,
    )

    def make(count):
        for i in range(count):
            Ticket.objects.create(
                contact=contact,
                subject=f"Request {i}",
                description="...",
                category=category,
                origin_channel=Ticket.Channel.EMAIL,
                department=department,
                branch=branch,
            )

    url = reverse("portal:home")

    make(3)
    with CaptureQueriesContext(connection) as few:
        assert client.get(url).status_code == 200

    make(20)
    with CaptureQueriesContext(connection) as many:
        assert client.get(url).status_code == 200

    assert len(many) == len(few), (
        f"{len(few)} queries for 3 requests and {len(many)} for 23. The list issues a query "
        "per row."
    )


@pytest.mark.django_db
def test_the_portal_request_detail_does_not_query_per_message(
    customer_client_for_budget, department, branch, category, agent
):
    from apps.customers.models import Contact, ContactDetail
    from apps.tickets.models import Message, Ticket

    client, account = customer_client_for_budget
    contact = Contact.objects.create(full_name="Noura", department=department, branch=branch)
    ContactDetail.objects.create(
        contact=contact,
        kind=ContactDetail.Kind.EMAIL,
        value=account.email,
        department=department,
        branch=branch,
    )
    ticket = Ticket.objects.create(
        contact=contact,
        subject="A long conversation",
        description="...",
        category=category,
        origin_channel=Ticket.Channel.EMAIL,
        department=department,
        branch=branch,
    )

    def reply(count):
        for i in range(count):
            Message.objects.create(
                ticket=ticket,
                author=agent,
                direction=Message.Direction.OUTBOUND,
                visibility=Message.Visibility.PUBLIC,
                channel=Ticket.Channel.EMAIL,
                body=f"Update {i}",
            )

    url = reverse("portal:request", args=[ticket.reference])

    reply(2)
    with CaptureQueriesContext(connection) as few:
        assert client.get(url).status_code == 200

    reply(20)
    with CaptureQueriesContext(connection) as many:
        assert client.get(url).status_code == 200

    assert len(many) == len(few), (
        f"{len(few)} queries for 2 messages and {len(many)} for 22. The thread issues a query "
        "per message — most likely the author on each one."
    )
