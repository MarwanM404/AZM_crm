"""FR-002, SC-003: known email matches; unknown email creates a contact with no organization."""

import pytest

from apps.customers.models import Contact, ContactDetail
from apps.customers.services.matching import find_or_create_contact


@pytest.mark.django_db
def test_unknown_email_creates_contact_with_no_organization(department, branch):
    contact, created = find_or_create_contact(
        full_name="Jane Doe", email="jane@example.com", department=department, branch=branch
    )
    assert created is True
    assert contact.organization is None
    assert contact.is_unlinked is True


@pytest.mark.django_db
def test_known_email_matches_existing_contact_without_duplicating(department, branch):
    first, _ = find_or_create_contact(
        full_name="Jane Doe", email="jane@example.com", department=department, branch=branch
    )
    second, created = find_or_create_contact(
        full_name="J. Doe", email="Jane@Example.com", department=department, branch=branch
    )
    assert created is False
    assert second.pk == first.pk
    assert Contact.objects.count() == 1
    assert second.full_name == "Jane Doe"  # not overwritten by the second submission's name


@pytest.mark.django_db
def test_email_is_normalized_to_lower_case(department, branch):
    find_or_create_contact(
        full_name="Jane Doe", email="Jane@EXAMPLE.com", department=department, branch=branch
    )
    detail = ContactDetail.objects.get(kind=ContactDetail.Kind.EMAIL)
    assert detail.value == "jane@example.com"
