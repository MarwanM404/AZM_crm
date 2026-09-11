"""contracts/http-endpoints.md: ticket detail, and the FR-024 scope rule."""

import pytest
from django.urls import reverse

from apps.tickets.models import Message


@pytest.mark.django_db
def test_detail_shows_ticket_and_customer_context(agent_client, ticket):
    response = agent_client.get(reverse("tickets:detail", args=[ticket.reference]))
    body = response.content.decode()

    assert response.status_code == 200
    assert ticket.subject in body
    assert ticket.contact.full_name in body


@pytest.mark.django_db
def test_out_of_scope_ticket_returns_404_not_403(agent_client, other_department_ticket):
    """FR-024: a 403 would confirm the ticket exists. Only a 404 discloses nothing."""
    response = agent_client.get(reverse("tickets:detail", args=[other_department_ticket.reference]))
    assert response.status_code == 404
    assert other_department_ticket.subject not in response.content.decode()


@pytest.mark.django_db
def test_detail_shows_both_public_and_internal_messages_to_staff(agent_client, agent, ticket):
    Message.objects.create(
        ticket=ticket,
        author=agent,
        direction=Message.Direction.OUTBOUND,
        visibility=Message.Visibility.PUBLIC,
        channel=ticket.origin_channel,
        body="Public reply to the customer.",
    )
    Message.objects.create(
        ticket=ticket,
        author=agent,
        direction=Message.Direction.OUTBOUND,
        visibility=Message.Visibility.INTERNAL,
        channel=ticket.origin_channel,
        body="Internal note for the team.",
    )

    body = agent_client.get(reverse("tickets:detail", args=[ticket.reference])).content.decode()

    assert "Public reply to the customer." in body
    assert "Internal note for the team." in body


@pytest.mark.django_db
def test_detail_shows_ticket_history(agent_client, agent, ticket):
    from apps.tickets.models import Ticket
    from apps.tickets.services.lifecycle import apply_transition

    apply_transition(ticket, Ticket.Status.OPEN, actor=agent)

    body = agent_client.get(reverse("tickets:detail", args=[ticket.reference])).content.decode()
    assert "Open" in body
