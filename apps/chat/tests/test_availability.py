"""
Is anyone there? (T101, T107, FR-001, FR-039)

The public site asks this on every page load, before deciding whether to render a chat
launcher at all. That single fact settles the implementation: it is a presence lookup, and it
must never grow into a query against conversation history. A question asked on every page
load of a public website is a question that will be asked far more often than anything else
in this product.
"""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.chat.services import presence
from apps.chat.services.redis_client import reset_for_tests

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clean():
    reset_for_tests()
    yield
    reset_for_tests()


def answer(client):
    return client.get(reverse("chat:availability")).json()["available"]


def test_nobody_online_means_no(client, agent, branch, department):
    assert answer(client) is False


def test_one_agent_online_means_yes(client, agent, branch, department):
    presence.go_online(agent.pk, capacity=3)

    assert answer(client) is True


def test_an_agent_at_capacity_still_means_yes(client, agent, branch, department):
    """FR-039 draws the line at "online", not "free". Queuing applies when agents are online
    and busy; the desk is only closed when nobody is there at all."""
    presence.go_online(agent.pk, capacity=1)
    presence.claim_slot(agent.pk)

    assert answer(client) is True


def test_an_agent_who_went_offline_means_no_again(client, agent, branch, department):
    presence.go_online(agent.pk, capacity=3)
    presence.go_offline(agent.pk)

    assert answer(client) is False


def test_a_lapsed_heartbeat_means_no(client, agent, branch, department):
    """An agent whose laptop slept is not online, and the presence key expiring is what says
    so — no sweep, no stale row (see presence.py)."""
    from apps.chat.services.redis_client import get_client

    presence.go_online(agent.pk, capacity=3)
    get_client().force_expire(f"chat:presence:{agent.pk}")

    assert answer(client) is False


def test_it_never_queries_conversation_history(client, agent, branch, department):
    """The guard that keeps this cheap. Asked on every public page load, so a join against
    conversations here would be the most-executed expensive query in the product."""
    presence.go_online(agent.pk, capacity=3)

    with CaptureQueriesContext(connection) as queries:
        client.get(reverse("chat:availability"))

    executed = " ".join(q["sql"].lower() for q in queries)
    assert "chat_conversation" not in executed
    assert "tickets_message" not in executed


def test_it_stays_a_small_number_of_queries(
    client, agent, branch, department, django_assert_num_queries
):
    presence.go_online(agent.pk, capacity=3)

    with django_assert_num_queries(3):
        client.get(reverse("chat:availability"))


def test_it_needs_no_session(client, agent, branch, department):
    """Answered for an anonymous visitor on a public page."""
    presence.go_online(agent.pk, capacity=3)

    response = client.get(reverse("chat:availability"))

    assert response.status_code == 200
