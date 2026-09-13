"""
The first administrator arrives with a scope (T020, FR-006).

The framework's own account-creation command asks for an email and a name, because those are
the only required fields. It cannot reasonably ask for a department: on an empty database there
is none to choose. So the first account is created without a scope, sees nothing, and the
person holding it concludes the product is broken — which is how this defect was reported.

The fix is a command that creates the scope and the account together. That order is the whole
point; there is no order in which the existing command could have worked.
"""

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.accounts.models import Branch, Department, User

pytestmark = pytest.mark.django_db


def test_it_creates_a_department_a_branch_and_an_administrator(db):
    call_command(
        "bootstrap_admin",
        email="first@example.com",
        full_name="First Administrator",
        department="Support",
        branch="Head Office",
    )

    created = User.objects.get(email="first@example.com")
    assert created.role == User.Role.ADMINISTRATOR
    assert created.department.name == "Support"
    assert created.branch.name == "Head Office"


def test_the_account_it_creates_can_see_its_own_screens(db, client):
    from django.urls import reverse

    call_command(
        "bootstrap_admin",
        email="first@example.com",
        full_name="First Administrator",
        department="Support",
        branch="Head Office",
    )
    created = User.objects.get(email="first@example.com")
    created.set_password("known-password")
    created.language = "en"
    created.save()

    client.force_login(created)
    body = client.get(reverse("administration:users")).content.decode()

    assert "First Administrator" in body
    assert "no department or branch" not in body.lower()


def test_it_reuses_a_department_that_already_exists(db):
    existing = Department.objects.create(name="Support")

    call_command(
        "bootstrap_admin",
        email="first@example.com",
        full_name="First Administrator",
        department="Support",
        branch="Head Office",
    )

    assert Department.objects.filter(name="Support").count() == 1
    assert User.objects.get(email="first@example.com").department_id == existing.pk


def test_it_refuses_to_create_an_account_without_a_scope(db):
    """The rule the framework's command cannot express."""
    with pytest.raises(CommandError):
        call_command(
            "bootstrap_admin",
            email="first@example.com",
            full_name="First Administrator",
            department="",
            branch="Head Office",
        )

    assert not User.objects.filter(email="first@example.com").exists()


def test_it_refuses_a_duplicate_email(db):
    call_command(
        "bootstrap_admin",
        email="first@example.com",
        full_name="First",
        department="Support",
        branch="Head Office",
    )

    with pytest.raises(CommandError):
        call_command(
            "bootstrap_admin",
            email="first@example.com",
            full_name="Second",
            department="Support",
            branch="Head Office",
        )

    assert User.objects.filter(email="first@example.com").count() == 1


def test_it_creates_nothing_when_it_refuses(db):
    """A half-run bootstrap leaves a department nobody asked for, on a database whose whole
    point was to be empty."""
    with pytest.raises(CommandError):
        call_command(
            "bootstrap_admin",
            email="",
            full_name="First",
            department="Support",
            branch="Head Office",
        )

    assert not Department.objects.exists()
    assert not Branch.objects.exists()
    assert not User.objects.exists()


def test_the_account_cannot_sign_in_until_a_password_is_set(db):
    """Same rule as every other account creation (MVP FR-025): creating an account never
    creates a way in."""
    call_command(
        "bootstrap_admin",
        email="first@example.com",
        full_name="First",
        department="Support",
        branch="Head Office",
    )

    assert not User.objects.get(email="first@example.com").has_usable_password()
