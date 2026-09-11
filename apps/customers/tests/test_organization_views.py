"""contracts/http-endpoints.md: the customer endpoints. FR-017, FR-018."""

import pytest
from django.urls import reverse

from apps.customers.models import Note, Organization


@pytest.fixture
def organization(db, department, branch):
    return Organization.objects.create(name="Najd Trading", department=department, branch=branch)


@pytest.mark.django_db
def test_list_shows_organizations_in_scope_only(
    agent_client, organization, other_department, branch
):
    hidden = Organization.objects.create(
        name="Other Department Co", department=other_department, branch=branch
    )
    body = agent_client.get(reverse("customers:list")).content.decode()
    assert organization.name in body
    assert hidden.name not in body


@pytest.mark.django_db
def test_detail_shows_organization_and_its_contacts(agent_client, organization, department, branch):
    from apps.customers.models import Contact

    Contact.objects.create(
        full_name="Sara Ahmed", organization=organization, department=department, branch=branch
    )
    body = agent_client.get(reverse("customers:detail", args=[organization.pk])).content.decode()
    assert organization.name in body
    assert "Sara Ahmed" in body


@pytest.mark.django_db
def test_agent_can_add_a_note(agent_client, agent, organization):
    response = agent_client.post(
        reverse("customers:note", args=[organization.pk]),
        {"body": "Called their operations lead about the recurring disputes."},
    )
    assert response.status_code in (200, 302)

    note = Note.objects.get()
    assert note.author == agent
    assert note.organization == organization


@pytest.mark.django_db
def test_empty_note_is_rejected(agent_client, organization):
    response = agent_client.post(reverse("customers:note", args=[organization.pk]), {"body": " "})
    assert response.status_code == 422
    assert not Note.objects.exists()


@pytest.mark.django_db
def test_agent_can_edit_organization_details(agent_client, organization):
    response = agent_client.post(
        reverse("customers:edit", args=[organization.pk]),
        {"name": "Najd Trading Co.", "name_ar": "شركة نجد التجارية"},
    )
    assert response.status_code in (200, 302)

    organization.refresh_from_db()
    assert organization.name == "Najd Trading Co."
    assert organization.name_ar == "شركة نجد التجارية"


@pytest.mark.django_db
def test_note_on_out_of_scope_organization_returns_404(agent_client, other_department, branch):
    hidden = Organization.objects.create(name="Hidden", department=other_department, branch=branch)
    response = agent_client.post(reverse("customers:note", args=[hidden.pk]), {"body": "x"})
    assert response.status_code == 404
    assert not Note.objects.exists()
