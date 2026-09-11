"""Spec US3 scenario 5: an organization with no activity says so, rather than looking broken."""

import pytest
from django.urls import reverse

from apps.customers.models import Organization


@pytest.mark.django_db
def test_organization_with_no_tickets_explains_the_empty_timeline(agent_client, department, branch):
    org = Organization.objects.create(name="Brand New Co", department=department, branch=branch)
    body = agent_client.get(reverse("customers:detail", args=[org.pk])).content.decode()
    assert "Nothing has happened" in body or "no activity" in body.lower()


@pytest.mark.django_db
def test_empty_customer_list_explains_itself(agent_client):
    body = agent_client.get(reverse("customers:list")).content.decode()
    assert "No customer organizations" in body


@pytest.mark.django_db
def test_empty_unlinked_list_explains_itself(agent_client):
    body = agent_client.get(reverse("customers:unlinked")).content.decode()
    assert "Every contact" in body or "no contacts" in body.lower()
