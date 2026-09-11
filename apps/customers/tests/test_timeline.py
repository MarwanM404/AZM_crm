"""FR-019: one timeline per organization, combining every contact's tickets with its notes."""

import pytest
from django.urls import reverse

from apps.customers.models import Contact, ContactDetail, Note, Organization
from apps.customers.services.timeline import timeline_for
from apps.tickets.models import Ticket


@pytest.fixture
def org_with_two_contacts(db, department, branch, category, agent):
    org = Organization.objects.create(name="Najd Trading", department=department, branch=branch)
    sara = Contact.objects.create(
        full_name="Sara Ahmed", organization=org, department=department, branch=branch
    )
    omar = Contact.objects.create(
        full_name="Omar Khalid", organization=org, department=department, branch=branch
    )
    ContactDetail.objects.create(
        contact=sara,
        kind=ContactDetail.Kind.EMAIL,
        value="sara@najd.example",
        department=department,
        branch=branch,
    )
    sara_ticket = Ticket.objects.create(
        contact=sara,
        organization=org,
        subject="Sara's ticket",
        description="...",
        category=category,
        origin_channel=Ticket.Channel.WEB_FORM,
        department=department,
        branch=branch,
    )
    omar_ticket = Ticket.objects.create(
        contact=omar,
        organization=org,
        subject="Omar's ticket",
        description="...",
        category=category,
        origin_channel=Ticket.Channel.WEB_FORM,
        department=department,
        branch=branch,
    )
    note = Note.objects.create(
        organization=org,
        author=agent,
        body="Called their ops lead.",
        department=department,
        branch=branch,
    )
    return org, sara, omar, sara_ticket, omar_ticket, note


@pytest.mark.django_db
def test_timeline_combines_every_contacts_tickets_with_notes(org_with_two_contacts):
    org, _sara, _omar, sara_ticket, omar_ticket, note = org_with_two_contacts

    entries = list(timeline_for(org))
    subjects = {getattr(e.obj, "subject", None) for e in entries}
    bodies = {getattr(e.obj, "body", None) for e in entries}

    assert sara_ticket.subject in subjects
    assert omar_ticket.subject in subjects
    assert note.body in bodies
    assert len(entries) == 3


@pytest.mark.django_db
def test_timeline_is_reverse_chronological(org_with_two_contacts):
    org = org_with_two_contacts[0]
    stamps = [e.at for e in timeline_for(org)]
    assert stamps == sorted(stamps, reverse=True)


@pytest.mark.django_db
def test_timeline_narrows_to_one_contact(org_with_two_contacts):
    org, sara, _omar, sara_ticket, omar_ticket, _note = org_with_two_contacts

    entries = list(timeline_for(org, contact=sara))
    subjects = {getattr(e.obj, "subject", None) for e in entries}

    assert sara_ticket.subject in subjects
    assert omar_ticket.subject not in subjects


@pytest.mark.django_db
def test_detail_page_renders_the_combined_timeline(agent_client, org_with_two_contacts):
    org, _sara, _omar, sara_ticket, omar_ticket, note = org_with_two_contacts

    body = agent_client.get(reverse("customers:detail", args=[org.pk])).content.decode()

    assert sara_ticket.reference in body
    assert omar_ticket.reference in body
    assert note.body in body


@pytest.mark.django_db
def test_out_of_scope_organization_returns_404(agent_client, other_department, branch):
    org = Organization.objects.create(name="Elsewhere", department=other_department, branch=branch)
    response = agent_client.get(reverse("customers:detail", args=[org.pk]))
    assert response.status_code == 404
    assert "Elsewhere" not in response.content.decode()
