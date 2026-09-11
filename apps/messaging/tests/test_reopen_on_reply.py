"""Spec edge case: a customer reply to a resolved or closed ticket must not be lost."""

import pytest

from apps.messaging.services.inbound import ingest
from apps.tickets.models import Ticket


def mail_for(ticket):
    return {
        "to": f"support+{ticket.reference}@example.com",
        "from": "sara@najd-trading.example",
        "subject": "Re: still broken",
        "body": "This is happening again.",
        "in_reply_to": "",
        "references": "",
    }


@pytest.mark.django_db
@pytest.mark.parametrize("start", [Ticket.Status.RESOLVED, Ticket.Status.CLOSED])
def test_inbound_reply_reopens_a_finished_ticket(ticket, department, branch, start):
    ticket.status = start
    ticket.save(update_fields=["status"])

    ingest(mail_for(ticket), department, branch)

    ticket.refresh_from_db()
    assert ticket.status == Ticket.Status.OPEN
    assert ticket.messages.count() == 1


@pytest.mark.django_db
def test_inbound_reply_to_an_open_ticket_leaves_status_alone(ticket, department, branch):
    ticket.status = Ticket.Status.PENDING_CUSTOMER
    ticket.save(update_fields=["status"])

    ingest(mail_for(ticket), department, branch)

    ticket.refresh_from_db()
    assert ticket.status == Ticket.Status.OPEN  # customer answered, so it is ours again
