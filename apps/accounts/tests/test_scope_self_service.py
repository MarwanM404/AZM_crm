"""
An administrator with no scope can give themselves one (T018, T019, FR-005).

This is the one place in the product where somebody changes their own scope, and it is a
deliberate narrowing of a rule rather than an exception to it. Everywhere else, scope is
administered by somebody else — which works right up to the case that produced this defect:
one administrator, no scope, and nobody else who could fix it. Requiring a second, already
scoped administrator assumes one exists, and on a new installation none does.

So: permitted only from *no* scope, never between scopes. An administrator who already has one
is in the ordinary case and the ordinary rule applies.

The escalation this defect could have produced is tested here too, because it is the tempting
wrong fix: treating a scopeless account as seeing everything would make the screens look right
and would invert deny-by-default (Constitution III).
"""

import pytest
from django.urls import reverse

from apps.accounts.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def scopeless_administrator(db):
    return User.objects.create_superuser(
        email="root@example.com", password="bootstrap-pw", full_name="Root", language="en"
    )


@pytest.fixture
def scopeless_client(scopeless_administrator):
    from django.test import Client

    own = Client()
    own.force_login(scopeless_administrator)
    return own


def test_a_scopeless_administrator_can_set_their_own_scope(
    scopeless_client, scopeless_administrator, department, branch
):
    response = scopeless_client.post(
        reverse("administration:own_scope"),
        {"department": department.pk, "branch": branch.pk},
    )
    scopeless_administrator.refresh_from_db()

    assert response.status_code in (302, 200)
    assert scopeless_administrator.department_id == department.pk
    assert scopeless_administrator.branch_id == branch.pk


def test_the_screens_work_immediately_afterwards(
    scopeless_client, scopeless_administrator, department, branch, ticket
):
    """The point of the whole story: recovery, not merely a saved field."""
    scopeless_client.post(
        reverse("administration:own_scope"),
        {"department": department.pk, "branch": branch.pk},
    )

    body = scopeless_client.get(reverse("tickets:queue")).content.decode()
    assert ticket.reference in body


def test_an_administrator_who_already_has_a_scope_cannot_change_their_own(
    admin_client_, administrator, other_department, branch
):
    """The narrowing. Self-service exists for a state nobody can escape, not as a way around
    having someone else administer you."""
    response = admin_client_.post(
        reverse("administration:own_scope"),
        {"department": other_department.pk, "branch": branch.pk},
    )
    administrator.refresh_from_db()

    assert response.status_code == 422
    assert administrator.department_id != other_department.pk


def test_it_cannot_be_used_a_second_time(
    scopeless_client, scopeless_administrator, department, other_department, branch
):
    """Once used it closes behind itself, because the account is no longer scopeless."""
    scopeless_client.post(
        reverse("administration:own_scope"),
        {"department": department.pk, "branch": branch.pk},
    )

    response = scopeless_client.post(
        reverse("administration:own_scope"),
        {"department": other_department.pk, "branch": branch.pk},
    )
    scopeless_administrator.refresh_from_db()

    assert response.status_code == 422
    assert scopeless_administrator.department_id == department.pk


def test_a_non_administrator_cannot_use_it(client, db, department, branch):
    """An agent stranded without a scope is a misconfiguration for an administrator to fix.
    Letting any account choose its own scope would make scoping advisory."""
    stranded = User.objects.create_user(
        email="stranded@example.com",
        password="x",
        full_name="Stranded",
        role=User.Role.AGENT,
        language="en",
    )
    client.force_login(stranded)

    response = client.post(
        reverse("administration:own_scope"),
        {"department": department.pk, "branch": branch.pk},
    )
    stranded.refresh_from_db()

    assert response.status_code in (403, 404)
    assert stranded.department_id is None


def test_an_incomplete_scope_is_refused(scopeless_client, scopeless_administrator, department):
    response = scopeless_client.post(
        reverse("administration:own_scope"), {"department": department.pk, "branch": ""}
    )
    scopeless_administrator.refresh_from_db()

    assert response.status_code == 422
    assert scopeless_administrator.department_id is None


# --- the escalation this defect could have produced ---


def test_a_scopeless_account_does_not_see_everything(
    scopeless_client, department, other_department, branch, ticket, contact
):
    """The tempting wrong fix. Treating "no scope" as "all scopes" makes every screen look
    correct and inverts deny-by-default: a misconfiguration becomes a privilege escalation,
    and the account it happens to is the most privileged one in the system.
    """
    from apps.tickets.models import Category, Ticket

    elsewhere = Category.objects.create(name="Elsewhere", department=other_department)
    hidden = Ticket.objects.create(
        contact=contact,
        subject="Another department's ticket",
        description="",
        category=elsewhere,
        origin_channel=Ticket.Channel.WEB_FORM,
        department=other_department,
        branch=branch,
    )

    body = scopeless_client.get(reverse("tickets:queue")).content.decode()

    assert ticket.reference not in body
    assert hidden.reference not in body


def test_a_scopeless_account_cannot_reach_a_record_directly(
    scopeless_client, ticket, department, branch
):
    """Not merely absent from the list — unreachable, and refused as not-found (MVP FR-024)."""
    response = scopeless_client.get(reverse("tickets:detail", args=[ticket.reference]))

    assert response.status_code == 404
