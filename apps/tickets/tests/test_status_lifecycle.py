"""FR-009: the status lifecycle is enforced; transitions outside it are rejected (422)."""

import pytest
from django.urls import reverse

from apps.tickets.models import Ticket
from apps.tickets.services.lifecycle import InvalidTransition, apply_transition


@pytest.mark.django_db
def test_permitted_transitions_succeed(ticket, agent):
    apply_transition(ticket, Ticket.Status.OPEN, actor=agent)
    assert ticket.status == Ticket.Status.OPEN

    apply_transition(ticket, Ticket.Status.PENDING_CUSTOMER, actor=agent)
    assert ticket.status == Ticket.Status.PENDING_CUSTOMER


@pytest.mark.django_db
def test_transition_outside_lifecycle_is_rejected(ticket, agent):
    # NEW -> CLOSED is not a permitted edge; a ticket is resolved before it is closed.
    with pytest.raises(InvalidTransition):
        apply_transition(ticket, Ticket.Status.CLOSED, actor=agent)
    ticket.refresh_from_db()
    assert ticket.status == Ticket.Status.NEW


@pytest.mark.django_db
def test_resolving_stamps_resolved_at(ticket, agent):
    apply_transition(ticket, Ticket.Status.RESOLVED, actor=agent)
    assert ticket.resolved_at is not None


@pytest.mark.django_db
def test_reopening_clears_resolved_at(ticket, agent):
    apply_transition(ticket, Ticket.Status.RESOLVED, actor=agent)
    apply_transition(ticket, Ticket.Status.OPEN, actor=agent)
    assert ticket.status == Ticket.Status.OPEN
    assert ticket.resolved_at is None


@pytest.mark.django_db
def test_endpoint_returns_422_for_invalid_transition(agent_client, ticket):
    response = agent_client.post(
        reverse("tickets:status", args=[ticket.reference]), {"status": Ticket.Status.CLOSED}
    )
    assert response.status_code == 422
    ticket.refresh_from_db()
    assert ticket.status == Ticket.Status.NEW


@pytest.mark.django_db
def test_endpoint_applies_valid_transition(agent_client, ticket):
    response = agent_client.post(
        reverse("tickets:status", args=[ticket.reference]), {"status": Ticket.Status.OPEN}
    )
    assert response.status_code == 200
    ticket.refresh_from_db()
    assert ticket.status == Ticket.Status.OPEN
