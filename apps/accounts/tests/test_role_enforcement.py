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
    """The record has to say enough to act on.

    With three roles, "someone was refused" is not useful on its own — the question is always
    which role tried what, and whether the refusal was correct. So the line carries the actor,
    their role, the path, and the roles that would have been allowed.
    """
    import logging

    with caplog.at_level(logging.WARNING):
        agent_client.get(reverse("administration:users"))

    refusals = [r for r in caplog.records if "Refused action" in r.message]
    assert refusals, "the refusal was not logged at all"

    recorded = str(refusals[0].args)
    assert str(agent.pk) in recorded, "the log does not say who was refused"
    assert "AGENT" in recorded, "the log does not say what role they held"
    assert "ADMINISTRATOR" in recorded, "the log does not say what would have been allowed"
