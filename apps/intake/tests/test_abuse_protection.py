"""
FR-006: limit abusive submission volume without turning away real customers.

Honeypot and minimum-completion-time checks are deterministic and tested here directly. The
Redis-backed rate limit's fail-open behaviour (research.md #6) is NOT exercised here: this
sandbox has no Redis server available, so django-ratelimit's cache backend falls back to
Django's locmem cache in settings.test, which cannot demonstrate a Redis outage. That specific
behaviour needs an integration test against a real Redis instance before release (tracked
alongside T143-T146 as an environment-dependent gap, not silently assumed to work).
"""

import time

import pytest
from django.urls import reverse

from apps.tickets.models import Ticket


def _payload(category, **overrides):
    payload = {
        "full_name": "Jane Doe",
        "email": "jane@example.com",
        "category": category.pk,
        "subject": "Help",
        "description": "Something broke",
        "company_website": "",
        "rendered_at": time.time() - 5,
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_honeypot_field_rejects_submission(client, branch, category):
    response = client.post(
        reverse("intake:form"), _payload(category, company_website="http://spam.example")
    )
    assert response.status_code == 200  # re-rendered, not redirected to success
    assert not Ticket.objects.exists()


@pytest.mark.django_db
def test_submission_faster_than_minimum_time_is_rejected(client, branch, category):
    response = client.post(reverse("intake:form"), _payload(category, rendered_at=time.time()))
    assert response.status_code == 200
    assert not Ticket.objects.exists()


@pytest.mark.django_db
def test_submission_slower_than_minimum_time_succeeds(client, branch, category):
    response = client.post(reverse("intake:form"), _payload(category, rendered_at=time.time() - 10))
    assert response.status_code == 302
    assert Ticket.objects.exists()
