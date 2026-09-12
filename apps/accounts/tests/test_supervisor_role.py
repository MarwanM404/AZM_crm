"""
The Supervisor role (FR-037).

A Supervisor works tickets like an Agent and additionally observes and coaches within their
own department — and explicitly cannot administer accounts or read the audit log, because
coaching an agent and administering the system are different jobs.

The last test here is the one that matters beyond this feature: it pins the *style* in which
permission checks are written. A check phrased as "not an Agent" would have silently admitted
Supervisors to administrator screens the moment the role existed.
"""

import re
from pathlib import Path

import pytest
from django.urls import reverse

from apps.accounts.models import User

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent


@pytest.fixture
def supervisor(db, department, branch):
    return User.objects.create_user(
        email="lead@example.com",
        password="pw",
        full_name="Team Lead",
        role=User.Role.SUPERVISOR,
        department=department,
        branch=branch,
        language="en",
    )


@pytest.fixture
def supervisor_client(db, supervisor):
    from django.test import Client

    client = Client()
    client.force_login(supervisor)
    return client


def test_the_role_exists_and_is_distinct():
    assert User.Role.SUPERVISOR not in (User.Role.AGENT, User.Role.ADMINISTRATOR)
    assert len(User.Role.choices) == 3


@pytest.mark.django_db
def test_agent_remains_the_default_role(department, branch):
    """Adding a role must not promote anyone. A new account is an Agent unless someone says
    otherwise."""
    user = User.objects.create_user(
        email="new@example.com",
        password="pw",
        full_name="New",
        department=department,
        branch=branch,
    )
    assert user.role == User.Role.AGENT


@pytest.mark.django_db
def test_a_supervisor_can_do_everything_an_agent_can(supervisor_client, ticket):
    assert supervisor_client.get(reverse("tickets:queue")).status_code == 200
    assert (
        supervisor_client.get(reverse("tickets:detail", args=[ticket.reference])).status_code == 200
    )
    assert supervisor_client.get(reverse("customers:list")).status_code == 200

    response = supervisor_client.post(
        reverse("tickets:reply", args=[ticket.reference]), {"body": "Handled."}
    )
    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize(
    "route", ["administration:users", "administration:user_new", "administration:audit"]
)
def test_a_supervisor_cannot_administer(supervisor_client, route):
    """The half of the role that is a restriction rather than a capability."""
    assert supervisor_client.get(reverse(route)).status_code == 403


@pytest.mark.django_db
def test_a_supervisor_cannot_deactivate_an_account(supervisor_client, agent):
    response = supervisor_client.post(reverse("administration:user_deactivate", args=[agent.pk]))
    assert response.status_code == 403
    agent.refresh_from_db()
    assert agent.is_active


@pytest.mark.django_db
def test_a_supervisor_cannot_delete_a_customer(supervisor_client, department, branch):
    from apps.customers.models import Organization

    org = Organization.objects.create(name="Najd", department=department, branch=branch)
    assert supervisor_client.post(reverse("customers:delete", args=[org.pk])).status_code == 403
    assert Organization.objects.filter(pk=org.pk).exists()


def test_no_permission_check_is_phrased_as_not_an_agent():
    """The audit from T017, made permanent.

    Every existing check was written as an allowlist — `role == ADMINISTRATOR` or
    `role != ADMINISTRATOR` — which is why adding a third role changed none of them. A check
    written the other way round, excluding Agent, would have admitted Supervisors to
    administrator screens the moment the role existed, silently and with no test failing.

    This scans for that shape so the next one is caught at the point it is written.
    """
    dangerous = re.compile(
        r"role\s*(!=|<>)\s*(User\.)?Role\.AGENT"  # role != Role.AGENT
        r"|role\s*!=\s*['\"]AGENT['\"]"  # role != "AGENT"
        r"|not\s+.*role\s*==\s*(User\.)?Role\.AGENT"  # not (role == Role.AGENT)
    )
    offenders = []
    for path in list((BASE_DIR / "apps").rglob("*.py")) + list(
        (BASE_DIR / "templates").rglob("*.html")
    ):
        if "/tests/" in str(path) or "/migrations/" in str(path):
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if dangerous.search(line):
                offenders.append(f"{path.relative_to(BASE_DIR)}:{lineno}: {line.strip()}")

    assert not offenders, (
        "A permission check excludes Agent rather than naming the roles it allows. With three "
        "roles that grants Supervisors whatever this protects. Name the allowed roles "
        "instead:\n  " + "\n  ".join(offenders)
    )
