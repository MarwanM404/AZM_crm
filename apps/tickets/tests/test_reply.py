"""FR-012, FR-010: agent replies and field changes land on the thread and the history."""

import pytest
from django.core import mail
from django.urls import reverse

from apps.tickets.models import Message, Ticket


@pytest.mark.django_db
def test_reply_is_recorded_on_the_thread_and_emailed(agent_client, agent, ticket):
    response = agent_client.post(
        reverse("tickets:reply", args=[ticket.reference]),
        {"body": "We have opened an investigation with the carrier."},
    )
    assert response.status_code == 200

    message = Message.objects.get(ticket=ticket)
    assert message.author == agent
    assert message.direction == Message.Direction.OUTBOUND
    assert message.visibility == Message.Visibility.PUBLIC
    assert len(mail.outbox) == 1
    assert "carrier" in mail.outbox[0].body


@pytest.mark.django_db
def test_empty_reply_is_rejected(agent_client, ticket):
    response = agent_client.post(reverse("tickets:reply", args=[ticket.reference]), {"body": "  "})
    assert response.status_code == 422
    assert not Message.objects.exists()


@pytest.mark.django_db
def test_first_reply_stamps_first_response_at(agent_client, ticket):
    agent_client.post(reverse("tickets:reply", args=[ticket.reference]), {"body": "On it."})
    ticket.refresh_from_db()
    assert ticket.first_response_at is not None


@pytest.mark.django_db
def test_replying_to_a_new_ticket_opens_it(agent_client, ticket):
    assert ticket.status == Ticket.Status.NEW
    agent_client.post(reverse("tickets:reply", args=[ticket.reference]), {"body": "On it."})
    ticket.refresh_from_db()
    assert ticket.status == Ticket.Status.OPEN


@pytest.mark.django_db
def test_reply_out_of_scope_returns_404(agent_client, other_department_ticket):
    response = agent_client.post(
        reverse("tickets:reply", args=[other_department_ticket.reference]), {"body": "hi"}
    )
    assert response.status_code == 404
    assert not Message.objects.exists()


@pytest.mark.django_db
def test_category_and_priority_changes_are_recorded(agent_client, ticket, other_department):
    from apps.tickets.models import Category

    new_category = Category.objects.create(name="Logistics", department=ticket.department)
    response = agent_client.post(
        reverse("tickets:fields", args=[ticket.reference]),
        {"category": new_category.pk, "priority": Ticket.Priority.URGENT},
    )
    assert response.status_code == 200

    ticket.refresh_from_db()
    assert ticket.category == new_category
    assert ticket.priority == Ticket.Priority.URGENT
