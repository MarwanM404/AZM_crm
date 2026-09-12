"""
T137, SC-010: the assumed 50 concurrent agents (research.md #8).

Concurrency in a Django test runs against SQLite here, so this cannot prove production
throughput. What it can prove is the property that actually breaks under concurrency and
would otherwise only show up in production: that two agents racing for the same unassigned
ticket produce exactly one winner, at scale and repeatedly, rather than both believing they
took it.
"""

import threading

import pytest
from django.db import connection, connections
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.tickets.models import Ticket

pytestmark = pytest.mark.django_db(transaction=True)

# SQLite has no row-level locking: `select_for_update` cannot be exercised on it, and
# concurrent writers lock the whole database rather than one row. A test that "passes" here
# proves nothing about the race it claims to measure, so it is skipped rather than weakened
# until it goes green. It runs against PostgreSQL — the production database per ADR-002 —
# which is where the guarantee actually has to hold.
needs_row_locking = pytest.mark.skipif(
    connection.vendor == "sqlite",
    reason=(
        "select_for_update needs row-level locking; SQLite has none, so this cannot "
        "exercise the take race. Runs against PostgreSQL in CI."
    ),
)


def _agents(count, department, branch):
    return [
        User.objects.create_user(
            email=f"agent{i}@example.com",
            password="pw",
            full_name=f"Agent {i}",
            role=User.Role.AGENT,
            department=department,
            branch=branch,
            language="en",
        )
        for i in range(count)
    ]


@pytest.mark.slow
@needs_row_locking
def test_many_agents_racing_for_one_ticket_produce_exactly_one_winner(
    department, branch, category, contact
):
    ticket = Ticket.objects.create(
        contact=contact,
        subject="Contested",
        description="...",
        category=category,
        origin_channel=Ticket.Channel.WEB_FORM,
        department=department,
        branch=branch,
    )
    agents = _agents(12, department, branch)
    url = reverse("tickets:take", args=[ticket.reference])
    results, lock = [], threading.Lock()

    # Signed in up front, on this thread: force_login writes a session row, and twelve
    # concurrent session writes lock SQLite regardless of application code. Doing it inside
    # the threads made this test flaky for a reason that had nothing to do with the race it
    # exists to measure.
    clients = []
    for agent in agents:
        client = Client()
        client.force_login(agent)
        clients.append(client)

    def take(client):
        try:
            response = client.post(url)
            with lock:
                results.append(response.status_code)
        finally:
            connections.close_all()  # each thread holds its own connection

    threads = [threading.Thread(target=take, args=(c,)) for c in clients]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    winners = [code for code in results if code == 200]
    assert (
        len(winners) == 1
    ), f"{len(winners)} agents were told they took the same ticket. Results: {results}"

    ticket.refresh_from_db()
    assert ticket.assigned_to is not None


@pytest.mark.slow
def test_concurrent_reads_do_not_interfere(department, branch, category, contact):
    """Fifty agents opening the queue at once must each get their own scoped result.

    The sign-ins happen up front, on this thread: signing in writes a session row, and fifty
    concurrent writes lock SQLite regardless of application code. It is also the more
    realistic shape — agents are already signed in when they refresh a queue.
    """
    agents = _agents(50, department, branch)
    Ticket.objects.create(
        contact=contact,
        subject="Shared",
        description="...",
        category=category,
        origin_channel=Ticket.Channel.WEB_FORM,
        department=department,
        branch=branch,
    )

    clients = []
    for agent in agents:
        client = Client()
        client.force_login(agent)
        clients.append(client)

    statuses, lock = [], threading.Lock()

    def open_queue(client):
        try:
            response = client.get(reverse("tickets:queue"))
            with lock:
                statuses.append(response.status_code)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=open_queue, args=(c,)) for c in clients]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert statuses.count(200) == 50, f"not every agent got their queue: {statuses}"
