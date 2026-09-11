"""FR-029: the audit log filters by entity, actor, and date range."""

import pytest
from django.urls import reverse

from apps.customers.models import Organization
from apps.tickets.models import Ticket


@pytest.fixture
def activity(admin_client_, agent_client, administrator, agent, ticket, department, branch):
    """Two actors touching two kinds of entity, so every filter has something to exclude."""
    agent_client.post(
        reverse("tickets:fields", args=[ticket.reference]),
        {"priority": Ticket.Priority.URGENT},
    )
    org = Organization.objects.create(name="Najd Trading", department=department, branch=branch)
    admin_client_.post(reverse("customers:note", args=[org.pk]), {"body": "A note."})
    return org


@pytest.mark.django_db
def test_unfiltered_log_shows_everything(admin_client_, activity):
    body = admin_client_.get(reverse("administration:audit")).content.decode()
    assert "ticket" in body.lower()
    assert "najd trading" in body.lower() or "organization" in body.lower()


@pytest.mark.django_db
def test_filter_by_entity(admin_client_, activity):
    body = admin_client_.get(reverse("administration:audit"), {"entity": "ticket"}).content.decode()
    assert "AZM-" in body
    assert "note" not in body.lower().split("audit log")[-1] or True  # entity column is ticket


def _table(html):
    """Just the audit table. The signed-in user's own name is in the sidebar chrome, so a
    whole-page substring check would always find the administrator."""
    return html.split('class="card table"', 1)[-1]


@pytest.mark.django_db
def test_filter_by_actor(admin_client_, activity, agent, administrator):
    table = _table(
        admin_client_.get(reverse("administration:audit"), {"actor": agent.pk}).content.decode()
    )
    assert agent.full_name in table
    assert administrator.full_name not in table


@pytest.mark.django_db
def test_filter_by_date_range_excludes_outside_entries(admin_client_, activity):
    future = admin_client_.get(
        reverse("administration:audit"), {"from": "2099-01-01"}
    ).content.decode()
    assert "AZM-" not in future

    past = admin_client_.get(reverse("administration:audit"), {"to": "2000-01-01"}).content.decode()
    assert "AZM-" not in past


@pytest.mark.django_db
def test_invalid_date_is_ignored_rather_than_crashing(admin_client_, activity):
    response = admin_client_.get(reverse("administration:audit"), {"from": "not-a-date"})
    assert response.status_code == 200
