"""FR-005: incomplete submissions are rejected with field-level errors, entered text kept."""

import time

import pytest
from django.urls import reverse

from apps.tickets.models import Ticket


@pytest.mark.django_db
def test_missing_required_field_is_rejected_with_field_error(client, branch, category):
    payload = {
        "full_name": "",  # missing
        "email": "jane@example.com",
        "category": category.pk,
        "subject": "Subject",
        "description": "Description",
        "company_website": "",
        "rendered_at": time.time() - 5,
    }
    response = client.post(reverse("intake:form"), payload)
    assert response.status_code == 200  # re-rendered with errors, not redirected
    assert not Ticket.objects.exists()
    assert "field-required" in response.content.decode() or response.context["form"].errors


@pytest.mark.django_db
def test_entered_content_is_preserved_on_validation_error(client, branch, category):
    payload = {
        "full_name": "",
        "email": "jane@example.com",
        "category": category.pk,
        "subject": "A very specific subject line",
        "description": "A very specific description",
        "company_website": "",
        "rendered_at": time.time() - 5,
    }
    response = client.post(reverse("intake:form"), payload)
    body = response.content.decode()
    assert "A very specific subject line" in body
    assert "A very specific description" in body
