"""contracts/http-endpoints.md: the agent queue. FR-011, FR-038."""

import pytest
from django.urls import reverse

from apps.tickets.models import Ticket


@pytest.mark.django_db
def test_queue_lists_all_tickets_in_the_agents_department(agent_client, ticket, other_agent):
    """FR-038: department-wide, not just the agent's own — this is what makes a shared
    pull queue workable."""
    ticket.assigned_to = other_agent
    ticket.save(update_fields=["assigned_to"])

    response = agent_client.get(reverse("tickets:queue"))

    assert response.status_code == 200
    assert ticket.reference in response.content.decode()


@pytest.mark.django_db
def test_queue_excludes_other_departments(agent_client, ticket, other_department_ticket):
    response = agent_client.get(reverse("tickets:queue"))
    body = response.content.decode()
    assert ticket.reference in body
    assert other_department_ticket.reference not in body


@pytest.mark.django_db
def test_queue_filters_to_assigned_to_me(
    agent_client, agent, ticket, other_agent, category, department, branch, contact
):
    mine = Ticket.objects.create(
        contact=contact,
        subject="Mine",
        description="...",
        category=category,
        origin_channel=Ticket.Channel.WEB_FORM,
        department=department,
        branch=branch,
        assigned_to=agent,
    )
    ticket.assigned_to = other_agent
    ticket.save(update_fields=["assigned_to"])

    response = agent_client.get(reverse("tickets:queue"), {"assigned": "me"})
    body = response.content.decode()

    assert mine.reference in body
    assert ticket.reference not in body


@pytest.mark.django_db
def test_queue_filters_by_status(agent_client, ticket):
    response = agent_client.get(reverse("tickets:queue"), {"status": Ticket.Status.RESOLVED})
    assert ticket.reference not in response.content.decode()


@pytest.mark.django_db
def test_queue_search_matches_reference_and_subject(agent_client, ticket):
    by_ref = agent_client.get(reverse("tickets:queue"), {"q": ticket.reference})
    assert ticket.reference in by_ref.content.decode()

    by_subject = agent_client.get(reverse("tickets:queue"), {"q": "Shipment"})
    assert ticket.reference in by_subject.content.decode()

    no_match = agent_client.get(reverse("tickets:queue"), {"q": "zzzz-no-such-thing"})
    assert ticket.reference not in no_match.content.decode()


@pytest.mark.django_db
def test_htmx_request_returns_only_the_list_fragment(agent_client, ticket):
    response = agent_client.get(reverse("tickets:queue"), HTTP_HX_REQUEST="true")
    body = response.content.decode()
    assert ticket.reference in body
    assert "<html" not in body.lower()  # fragment only, no full page shell


@pytest.mark.django_db
def test_anonymous_visitor_is_redirected_to_sign_in(client, ticket):
    response = client.get(reverse("tickets:queue"))
    assert response.status_code == 302
    assert reverse("accounts:sign_in") in response.url
