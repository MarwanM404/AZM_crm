"""FR-020: soft deletion hides, retains, audits — and does not block reuse of a natural key."""

import pytest
from auditlog.models import LogEntry
from django.urls import reverse

from apps.customers.models import ContactDetail, Organization
from apps.customers.services.matching import find_or_create_contact


@pytest.fixture
def organization(db, department, branch):
    return Organization.objects.create(name="Najd Trading", department=department, branch=branch)


@pytest.mark.django_db
def test_administrator_can_soft_delete_an_organization(admin_client_, organization):
    response = admin_client_.post(reverse("customers:delete", args=[organization.pk]))
    assert response.status_code in (200, 302)

    assert not Organization.objects.filter(pk=organization.pk).exists()  # hidden
    assert Organization.all_objects.filter(pk=organization.pk).exists()  # retained


@pytest.mark.django_db
def test_agent_cannot_delete(agent_client, organization):
    response = agent_client.post(reverse("customers:delete", args=[organization.pk]))
    assert response.status_code == 403
    assert Organization.objects.filter(pk=organization.pk).exists()


@pytest.mark.django_db
def test_deletion_records_who_and_is_audited(admin_client_, administrator, organization):
    admin_client_.post(reverse("customers:delete", args=[organization.pk]))

    deleted = Organization.all_objects.get(pk=organization.pk)
    assert deleted.deleted_by == administrator
    assert deleted.deleted_at is not None
    assert LogEntry.objects.get_for_object(organization).exists()


@pytest.mark.django_db
def test_deleted_organization_disappears_from_the_list(admin_client_, organization):
    admin_client_.post(reverse("customers:delete", args=[organization.pk]))
    body = admin_client_.get(reverse("customers:list")).content.decode()
    assert organization.name not in body


@pytest.mark.django_db
def test_soft_deleting_a_contact_frees_its_email_for_reuse(department, branch, agent):
    """The partial unique index is conditioned on deleted_at IS NULL. Without that, a deleted
    contact would permanently block its own email address, and the bug would surface as
    'the form will not accept my address'."""
    first, _ = find_or_create_contact(
        full_name="Sara", email="sara@example.com", department=department, branch=branch
    )
    detail = ContactDetail.objects.get(value="sara@example.com")
    detail.soft_delete(by=agent)
    first.soft_delete(by=agent)

    second, created = find_or_create_contact(
        full_name="Sara Again", email="sara@example.com", department=department, branch=branch
    )
    assert created is True
    assert second.pk != first.pk
