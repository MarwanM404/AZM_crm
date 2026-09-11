"""FR-014, FR-015: internal notes are staff-only and never emailed."""

import pytest
from django.core import mail
from django.urls import reverse

from apps.tickets.models import Message


@pytest.mark.django_db
def test_internal_note_is_stored_as_internal(agent_client, agent, ticket):
    response = agent_client.post(
        reverse("tickets:note", args=[ticket.reference]),
        {"body": "Carrier signature does not match any known contact."},
    )
    assert response.status_code == 200

    message = Message.objects.get(ticket=ticket)
    assert message.visibility == Message.Visibility.INTERNAL
    assert message.author == agent


@pytest.mark.django_db
def test_internal_note_sends_no_email(agent_client, ticket):
    agent_client.post(reverse("tickets:note", args=[ticket.reference]), {"body": "Team only."})
    assert mail.outbox == []


@pytest.mark.django_db
def test_internal_note_does_not_change_ticket_status(agent_client, ticket):
    before = ticket.status
    agent_client.post(reverse("tickets:note", args=[ticket.reference]), {"body": "Team only."})
    ticket.refresh_from_db()
    assert ticket.status == before


@pytest.mark.django_db
def test_internal_note_out_of_scope_returns_404(agent_client, other_department_ticket):
    response = agent_client.post(
        reverse("tickets:note", args=[other_department_ticket.reference]), {"body": "x"}
    )
    assert response.status_code == 404
    assert not Message.objects.exists()
