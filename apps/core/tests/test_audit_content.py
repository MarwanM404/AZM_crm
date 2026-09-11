"""FR-027: every entry carries actor, UTC timestamp, entity, action, and before/after values."""

import pytest
from auditlog.models import LogEntry
from django.urls import reverse
from django.utils import timezone

from apps.tickets.models import Ticket


@pytest.mark.django_db
def test_a_field_change_records_both_values(agent_client, ticket):
    agent_client.post(
        reverse("tickets:fields", args=[ticket.reference]),
        {"priority": Ticket.Priority.URGENT},
    )

    entry = LogEntry.objects.get_for_object(ticket).filter(action=LogEntry.Action.UPDATE).first()
    assert entry is not None
    before, after = entry.changes_dict["priority"]
    assert before == Ticket.Priority.NORMAL
    assert after == Ticket.Priority.URGENT


@pytest.mark.django_db
def test_entry_records_the_acting_user(agent_client, agent, ticket):
    agent_client.post(
        reverse("tickets:fields", args=[ticket.reference]),
        {"priority": Ticket.Priority.HIGH},
    )
    entry = LogEntry.objects.get_for_object(ticket).filter(action=LogEntry.Action.UPDATE).first()
    assert entry.actor == agent


@pytest.mark.django_db
def test_entry_timestamp_is_utc_and_recent(agent_client, ticket):
    agent_client.post(
        reverse("tickets:fields", args=[ticket.reference]),
        {"priority": Ticket.Priority.HIGH},
    )
    entry = LogEntry.objects.get_for_object(ticket).filter(action=LogEntry.Action.UPDATE).first()

    assert entry.timestamp.tzinfo is not None
    assert entry.timestamp.utcoffset().total_seconds() == 0
    assert (timezone.now() - entry.timestamp).total_seconds() < 60


@pytest.mark.django_db
def test_entry_identifies_the_entity(agent_client, ticket):
    agent_client.post(
        reverse("tickets:fields", args=[ticket.reference]),
        {"priority": Ticket.Priority.HIGH},
    )
    entry = LogEntry.objects.get_for_object(ticket).filter(action=LogEntry.Action.UPDATE).first()
    assert entry.content_type.model == "ticket"
    assert str(entry.object_pk) == str(ticket.pk)


@pytest.mark.django_db
def test_creation_and_soft_deletion_are_both_recorded(
    admin_client_, administrator, department, branch
):
    from apps.customers.models import Organization

    org = Organization.objects.create(name="Najd", department=department, branch=branch)
    admin_client_.post(reverse("customers:delete", args=[org.pk]))

    actions = {e.action for e in LogEntry.objects.get_for_object(org)}
    assert LogEntry.Action.CREATE in actions
    assert LogEntry.Action.UPDATE in actions  # soft delete is an update to deleted_at

    deletion = LogEntry.objects.get_for_object(org).filter(action=LogEntry.Action.UPDATE).first()
    assert "deleted_at" in deletion.changes_dict
    assert deletion.actor == administrator
