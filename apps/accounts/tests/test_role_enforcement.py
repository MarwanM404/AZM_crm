"""FR-021, FR-022: an agent attempting an administrator action is refused and recorded."""

import pytest
from django.urls import reverse

from apps.customers.models import Organization

ADMIN_ONLY: list[tuple[str, dict]] = [
    ("administration:users", {}),
    ("administration:user_new", {}),
]


@pytest.mark.django_db
@pytest.mark.parametrize("name,kwargs", ADMIN_ONLY)
def test_agent_is_refused_administrator_screens(agent_client, name, kwargs):
    response = agent_client.get(reverse(name, kwargs=kwargs))
    assert response.status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize("name,kwargs", ADMIN_ONLY)
def test_administrator_is_allowed(admin_client_, name, kwargs):
    response = admin_client_.get(reverse(name, kwargs=kwargs))
    assert response.status_code == 200


@pytest.mark.django_db
def test_agent_cannot_delete_an_organization(agent_client, department, branch):
    org = Organization.objects.create(name="Najd", department=department, branch=branch)
    response = agent_client.post(reverse("customers:delete", args=[org.pk]))
    assert response.status_code == 403
    assert Organization.objects.filter(pk=org.pk).exists()


@pytest.mark.django_db
def test_refused_attempt_is_recorded(agent_client, agent, caplog):
    import logging

    with caplog.at_level(logging.WARNING):
        agent_client.get(reverse("administration:users"))

    assert any("Refused administrator action" in r.message for r in caplog.records)
    assert any(str(agent.pk) in str(r.args) for r in caplog.records)
