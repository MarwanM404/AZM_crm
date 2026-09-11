"""FR-025, FR-026: administrators manage staff accounts; deactivation is immediate."""

import pytest
from auditlog.models import LogEntry
from django.urls import reverse

from apps.accounts.models import User


@pytest.mark.django_db
def test_administrator_can_list_users_in_scope(admin_client_, agent, other_department_agent):
    body = admin_client_.get(reverse("administration:users")).content.decode()
    assert agent.full_name in body
    assert other_department_agent.full_name not in body  # FR-023 applies to staff too


@pytest.mark.django_db
def test_creating_a_user_requires_a_role_and_a_department(admin_client_, department, branch):
    response = admin_client_.post(
        reverse("administration:user_new"),
        {
            "email": "new@example.com",
            "full_name": "New Agent",
            "role": User.Role.AGENT,
            "department": department.pk,
            "branch": branch.pk,
        },
    )
    assert response.status_code in (200, 302)

    created = User.objects.get(email="new@example.com")
    assert created.role == User.Role.AGENT
    assert created.department == department
    assert created.branch == branch


@pytest.mark.django_db
def test_a_new_account_cannot_sign_in_until_a_password_is_set(
    admin_client_, client, department, branch
):
    admin_client_.post(
        reverse("administration:user_new"),
        {
            "email": "new@example.com",
            "full_name": "New Agent",
            "role": User.Role.AGENT,
            "department": department.pk,
            "branch": branch.pk,
        },
    )
    created = User.objects.get(email="new@example.com")
    assert not created.has_usable_password()

    signed_in = client.login(email="new@example.com", password="")
    assert signed_in is False


@pytest.mark.django_db
def test_creating_a_user_without_a_department_is_rejected(admin_client_, branch):
    response = admin_client_.post(
        reverse("administration:user_new"),
        {
            "email": "nodept@example.com",
            "full_name": "No Dept",
            "role": User.Role.AGENT,
            "branch": branch.pk,
        },
    )
    assert response.status_code == 422
    assert not User.objects.filter(email="nodept@example.com").exists()


@pytest.mark.django_db
def test_deactivation_blocks_the_next_request_immediately(client, admin_client_, agent):
    """FR-026: not at next sign-in — on the very next request."""
    client.force_login(agent)
    assert client.get(reverse("tickets:queue")).status_code == 200

    admin_client_.post(reverse("administration:user_deactivate", args=[agent.pk]))

    response = client.get(reverse("tickets:queue"))
    assert response.status_code == 302
    assert reverse("accounts:sign_in") in response.url


@pytest.mark.django_db
def test_deactivation_is_audited(admin_client_, agent):
    admin_client_.post(reverse("administration:user_deactivate", args=[agent.pk]))
    assert LogEntry.objects.get_for_object(agent).exists()


@pytest.mark.django_db
def test_agent_cannot_deactivate_anyone(agent_client, other_agent):
    response = agent_client.post(reverse("administration:user_deactivate", args=[other_agent.pk]))
    assert response.status_code == 403
    other_agent.refresh_from_db()
    assert other_agent.is_active
