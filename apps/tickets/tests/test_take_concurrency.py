"""FR-008, FR-039: an agent takes an unassigned ticket; a second taker gets 409."""

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_taking_an_unassigned_ticket_assigns_it(agent_client, agent, ticket):
    response = agent_client.post(reverse("tickets:take", args=[ticket.reference]))
    assert response.status_code == 200
    ticket.refresh_from_db()
    assert ticket.assigned_to == agent


@pytest.mark.django_db
def test_second_take_of_an_assigned_ticket_returns_409(client, agent, other_agent, ticket):
    client.force_login(agent)
    first = client.post(reverse("tickets:take", args=[ticket.reference]))
    assert first.status_code == 200

    client.force_login(other_agent)
    second = client.post(reverse("tickets:take", args=[ticket.reference]))
    assert second.status_code == 409

    ticket.refresh_from_db()
    assert ticket.assigned_to == agent  # the first taker keeps it


@pytest.mark.django_db
def test_administrator_can_reassign_an_assigned_ticket(admin_client_, agent, other_agent, ticket):
    ticket.assigned_to = agent
    ticket.save(update_fields=["assigned_to"])

    response = admin_client_.post(
        reverse("tickets:assign", args=[ticket.reference]), {"agent": other_agent.pk}
    )
    assert response.status_code == 200
    ticket.refresh_from_db()
    assert ticket.assigned_to == other_agent


@pytest.mark.django_db
def test_agent_cannot_reassign(agent_client, agent, other_agent, ticket):
    ticket.assigned_to = agent
    ticket.save(update_fields=["assigned_to"])

    response = agent_client.post(
        reverse("tickets:assign", args=[ticket.reference]), {"agent": other_agent.pk}
    )
    assert response.status_code == 403
    ticket.refresh_from_db()
    assert ticket.assigned_to == agent
