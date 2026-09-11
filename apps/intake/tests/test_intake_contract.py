"""contracts/http-endpoints.md public endpoints: GET/POST /request/, GET /request/submitted/."""

import time

import pytest
from django.urls import reverse

from apps.tickets.models import Ticket


def _valid_payload(category):
    return {
        "full_name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "",
        "category": category.pk,
        "subject": "My widget is broken",
        "description": "It stopped working yesterday.",
        "company_website": "",
        "rendered_at": time.time() - 5,
    }


@pytest.mark.django_db
def test_get_request_form_renders(client):
    response = client.get(reverse("intake:form"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_valid_submission_creates_ticket_and_redirects(client, branch, category):
    response = client.post(reverse("intake:form"), _valid_payload(category))
    assert response.status_code == 302
    ticket = Ticket.objects.get()
    assert response.url == reverse("intake:submitted", args=[ticket.reference])
    assert ticket.contact.full_name == "Jane Doe"
    assert ticket.status == Ticket.Status.NEW
    assert ticket.origin_channel == Ticket.Channel.WEB_FORM


@pytest.mark.django_db
def test_confirmation_page_discloses_only_the_reference(client, branch, category):
    client.post(reverse("intake:form"), _valid_payload(category))
    ticket = Ticket.objects.get()

    response = client.get(reverse("intake:submitted", args=[ticket.reference]))

    assert response.status_code == 200
    body = response.content.decode()
    assert ticket.reference in body
    assert ticket.contact.full_name not in body
    assert "example.com" not in body  # the submitter's own email must not appear either


@pytest.mark.django_db
def test_submitted_page_404s_for_unknown_reference(client):
    response = client.get(reverse("intake:submitted", args=["AZM-2026-999999"]))
    assert response.status_code == 404
