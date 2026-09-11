"""
FR-041, FR-042: linking a contact that arrived without an employer, and moving one later.

These two are deliberately different operations:

- LINKING an unlinked contact backfills the tickets it raised, because a ticket with no
  organization has no history to protect — filling it in is a correction.
- MOVING a contact between organizations leaves existing tickets alone, because a ticket
  raised under one organization did happen under that organization; rewriting it would make
  the record untrue.
"""

import pytest
from auditlog.models import LogEntry
from django.urls import reverse

from apps.customers.models import Contact, Organization


@pytest.mark.django_db
def test_unlinked_contacts_are_listed_for_staff(agent_client, contact):
    assert contact.organization is None
    response = agent_client.get(reverse("customers:unlinked"))
    assert response.status_code == 200
    assert contact.full_name in response.content.decode()


@pytest.mark.django_db
def test_linking_backfills_tickets_that_had_no_organization(
    agent_client, contact, ticket, department, branch
):
    org = Organization.objects.create(name="Najd Trading", department=department, branch=branch)
    assert ticket.organization is None

    response = agent_client.post(
        reverse("customers:link_contact", args=[contact.pk]), {"organization": org.pk}
    )
    assert response.status_code in (200, 302)

    contact.refresh_from_db()
    ticket.refresh_from_db()
    assert contact.organization == org
    assert ticket.organization == org  # correction: it never had one


@pytest.mark.django_db
def test_linking_can_create_a_new_organization(agent_client, contact):
    response = agent_client.post(
        reverse("customers:link_contact", args=[contact.pk]), {"new_organization": "Rawabi Foods"}
    )
    assert response.status_code in (200, 302)

    contact.refresh_from_db()
    assert contact.organization is not None
    assert contact.organization.name == "Rawabi Foods"


@pytest.mark.django_db
def test_linking_is_audited(agent_client, contact, department, branch):
    org = Organization.objects.create(name="Najd Trading", department=department, branch=branch)
    agent_client.post(
        reverse("customers:link_contact", args=[contact.pk]), {"organization": org.pk}
    )
    entries = LogEntry.objects.get_for_object(contact)
    assert entries.exists()


@pytest.mark.django_db
def test_moving_a_contact_does_not_rewrite_existing_tickets(
    agent_client, contact, ticket, department, branch
):
    """FR-042: the ticket keeps the organization it was actually raised under."""
    first = Organization.objects.create(name="Najd Trading", department=department, branch=branch)
    second = Organization.objects.create(name="Rawabi Foods", department=department, branch=branch)

    agent_client.post(
        reverse("customers:link_contact", args=[contact.pk]), {"organization": first.pk}
    )
    ticket.refresh_from_db()
    assert ticket.organization == first

    agent_client.post(
        reverse("customers:link_contact", args=[contact.pk]), {"organization": second.pk}
    )

    contact.refresh_from_db()
    ticket.refresh_from_db()
    assert contact.organization == second  # the contact moved
    assert ticket.organization == first  # the ticket's history did not


@pytest.mark.django_db
def test_linking_out_of_scope_contact_returns_404(agent_client, other_department, branch):
    stranger = Contact.objects.create(
        full_name="Out of scope", department=other_department, branch=branch
    )
    response = agent_client.post(
        reverse("customers:link_contact", args=[stranger.pk]), {"new_organization": "Nope"}
    )
    assert response.status_code == 404
    stranger.refresh_from_db()
    assert stranger.organization is None
