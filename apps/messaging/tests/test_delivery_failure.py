"""FR-016: a delivery failure is visible on the ticket; the message stays on the thread."""

from unittest import mock

import pytest
from django.urls import reverse

from apps.tickets.models import Message


@pytest.mark.django_db
def test_permanent_failure_is_recorded_on_the_message(agent_client, ticket):
    with mock.patch(
        "django.core.mail.EmailMultiAlternatives.send", side_effect=OSError("mailbox unavailable")
    ):
        agent_client.post(reverse("tickets:reply", args=[ticket.reference]), {"body": "Hello"})

    message = Message.objects.get(ticket=ticket)
    assert message.delivery_status == Message.DeliveryStatus.FAILED
    assert "mailbox unavailable" in message.delivery_error


@pytest.mark.django_db
def test_failed_message_remains_on_the_thread(agent_client, ticket):
    with mock.patch("django.core.mail.EmailMultiAlternatives.send", side_effect=OSError("nope")):
        agent_client.post(reverse("tickets:reply", args=[ticket.reference]), {"body": "Hello"})

    assert ticket.messages.count() == 1  # not rolled back, not discarded


@pytest.mark.django_db
def test_failure_is_visible_to_the_agent_on_the_ticket(agent_client, ticket):
    with mock.patch("django.core.mail.EmailMultiAlternatives.send", side_effect=OSError("nope")):
        agent_client.post(reverse("tickets:reply", args=[ticket.reference]), {"body": "Hello"})

    body = agent_client.get(reverse("tickets:detail", args=[ticket.reference])).content.decode()
    assert "not delivered" in body.lower() or "failed" in body.lower()


@pytest.mark.django_db
def test_successful_send_marks_the_message_sent(agent_client, ticket):
    agent_client.post(reverse("tickets:reply", args=[ticket.reference]), {"body": "Hello"})
    assert Message.objects.get(ticket=ticket).delivery_status == Message.DeliveryStatus.SENT
