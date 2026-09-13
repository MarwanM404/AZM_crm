"""
One-click sign-in for testing, and its absence everywhere that matters (T046-T051).

This is the only story in this feature that adds something rather than fixing something, and
the only one that can do harm. A button that signs anyone in as an administrator is an
authentication bypass wearing a convenience's clothes, so the tests below are written around
the failure rather than around the feature.

The order is deliberate. `test_the_route_refuses_when_disabled` matters more than
`test_each_role_can_be_signed_in_as`: hiding a control does not disable the route behind it,
and a route that works when its control is hidden is a route somebody will find.

What makes the feature safe to have at all is that it offers only the demonstration accounts,
whose passwords are already in this repository. It discloses nothing that is not already
disclosed. Pointed at a real account it would be an authentication bypass outright, which is
why FR-019 forbids it rather than discouraging it.
"""

import re

import pytest
from django.test import override_settings
from django.urls import reverse

from apps.accounts.models import User

pytestmark = pytest.mark.django_db

ENABLED = override_settings(QUICK_SIGN_IN_ENABLED=True)


@pytest.fixture
def demo_accounts(db, department, branch):
    """Exactly what `seed_demo` creates."""
    return {
        role: User.objects.create_user(
            email=email,
            password="demo-password-change-me",
            full_name=f"Demo {role.title()}",
            role=role,
            department=department,
            branch=branch,
        )
        for role, email in (
            (User.Role.AGENT, "agent@example.com"),
            (User.Role.SUPERVISOR, "supervisor@example.com"),
            (User.Role.ADMINISTRATOR, "admin@example.com"),
        )
    }


def quick_sign_in(client, role):
    return client.post(reverse("accounts:quick_sign_in", args=[role]))


# --- the refusals, first, because they are what makes the rest acceptable ---


def test_the_route_refuses_when_disabled(client, demo_accounts):
    """FR-018. Called directly, with no control rendered anywhere on any page.

    This is the test that would be skipped as redundant once the button is correctly hidden,
    and it is the one protecting the product.
    """
    response = quick_sign_in(client, User.Role.ADMINISTRATOR)

    assert response.status_code in (403, 404)
    assert "_auth_user_id" not in client.session


def test_no_control_is_rendered_when_disabled(client):
    body = client.get(reverse("accounts:sign_in")).content.decode()

    assert reverse("accounts:quick_sign_in", args=[User.Role.AGENT]) not in body


def test_production_sets_it_off_literally(settings):
    """FR-017, asserted on the source rather than on an imported value.

    Importing the module would prove the setting is off under whatever environment the test
    process happens to have. The requirement is stronger and is about the source itself: the
    assignment must be a literal, because the risk is a deployment where somebody set an
    environment variable. A value read from the environment can be off in the test process and
    on in production, and the import would say nothing about that.
    """
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[3] / "config" / "settings" / "production.py"
    ).read_text()

    # Every assignment, compared whole. A pattern with a negative lookahead was tried first
    # and quietly matched the correct source: `\s*` can consume nothing, so the lookahead
    # examined a space rather than the value. Comparing the lines leaves nothing to backtrack.
    assignments = [
        line.strip()
        for line in source.splitlines()
        if re.match(r"\s*QUICK_SIGN_IN_ENABLED\s*=", line)
    ]

    assert assignments == ["QUICK_SIGN_IN_ENABLED = False"], (
        f"production assigns QUICK_SIGN_IN_ENABLED as {assignments}. It must be the literal "
        "False: a value read from the environment can be off in this test process and on in "
        "production, where one mistyped deployment variable would put one-click "
        "administrator access on a public page."
    )


def test_production_cannot_be_talked_into_enabling_it(monkeypatch):
    """The same guarantee from the other side: import it with the environment set every way
    somebody might try, and confirm the value does not move."""
    import importlib

    # Production requires every value from the environment by design, so importing it needs
    # them present. None of these are real; the module is imported to read one constant.
    for name, value in {
        "DJANGO_SECRET_KEY": "not-a-real-key-for-an-import-test",
        "DJANGO_ALLOWED_HOSTS": "example.com",
        "DATABASE_NAME": "x",
        "DATABASE_USER": "x",
        "DATABASE_PASSWORD": "x",
        "DATABASE_HOST": "localhost",
        "DATABASE_PORT": "5432",
        "REDIS_URL": "redis://localhost:6379/0",
        "EMAIL_HOST": "localhost",
        "EMAIL_HOST_USER": "x",
        "EMAIL_HOST_PASSWORD": "x",
        "DEFAULT_FROM_EMAIL": "x@example.com",
        "INBOUND_WEBHOOK_SECRET": "x",
    }.items():
        monkeypatch.setenv(name, value)

    for value in ("1", "true", "True", "yes", "on"):
        monkeypatch.setenv("QUICK_SIGN_IN_ENABLED", value)
        production = importlib.import_module("config.settings.production")
        importlib.reload(production)
        assert production.QUICK_SIGN_IN_ENABLED is False, (
            f"QUICK_SIGN_IN_ENABLED={value!r} in the environment enabled one-click sign-in "
            "in production"
        )


def test_it_is_disabled_by_default(settings):
    """FR-016. A convenience that is on unless switched off is on in the places nobody
    remembered to switch it off."""
    import importlib

    base = importlib.import_module("config.settings.base")

    assert base.QUICK_SIGN_IN_ENABLED is False


# --- what it does when it is enabled ---


@ENABLED
@pytest.mark.parametrize("role", [User.Role.AGENT, User.Role.SUPERVISOR, User.Role.ADMINISTRATOR])
def test_each_role_can_be_signed_in_as(client, demo_accounts, role):
    response = quick_sign_in(client, role)

    assert response.status_code in (302, 200)
    assert int(client.session["_auth_user_id"]) == demo_accounts[role].pk


@ENABLED
def test_the_controls_appear(client, demo_accounts):
    body = client.get(reverse("accounts:sign_in")).content.decode()

    for role in (User.Role.AGENT, User.Role.SUPERVISOR, User.Role.ADMINISTRATOR):
        assert reverse("accounts:quick_sign_in", args=[role]) in body


@ENABLED
def test_it_never_signs_in_a_real_account(client, demo_accounts, department, branch):
    """FR-019. The accounts it offers are named in configuration, not found by role — asking
    for a role must not mean "whichever account happens to hold it".

    The colleague below is created explicitly rather than taken from the shared `agent`
    fixture, which happens to use the same address as the seeded demonstration agent. Reusing
    it would have made this test pass while proving nothing.
    """
    # Note for anyone strengthening this: with the demonstration account present, a
    # role-based lookup happens to return it first, so this test alone does not distinguish
    # "looked up by name" from "looked up by role and got lucky". The test below —
    # test_an_account_not_in_the_demonstration_set_is_refused — removes the luck by taking the
    # demonstration account away, and that is the one that fails when the lookup changes.
    real = User.objects.create_user(
        email="layla.real@example.com",
        password="x",
        full_name="Layla Real",
        role=User.Role.AGENT,
        department=department,
        branch=branch,
    )

    quick_sign_in(client, User.Role.AGENT)

    assert int(client.session["_auth_user_id"]) != real.pk
    assert int(client.session["_auth_user_id"]) == demo_accounts[User.Role.AGENT].pk


@ENABLED
def test_an_account_not_in_the_demonstration_set_is_refused(client, department, branch):
    """Asked for a role that exists but whose demonstration account does not."""
    User.objects.create_user(
        email="someone.real@example.com",
        password="x",
        full_name="Someone Real",
        role=User.Role.AGENT,
        department=department,
        branch=branch,
    )

    response = quick_sign_in(client, User.Role.AGENT)

    assert response.status_code in (404, 422)
    assert "_auth_user_id" not in client.session


@ENABLED
def test_a_missing_demonstration_account_fails_visibly(client, demo_accounts):
    """Renamed or deleted since the data was seeded. It must say so rather than sign somebody
    in as whoever is nearest."""
    demo_accounts[User.Role.AGENT].delete()

    response = quick_sign_in(client, User.Role.AGENT)

    assert response.status_code in (404, 422)
    assert "_auth_user_id" not in client.session


@ENABLED
def test_an_unknown_role_is_refused(client, demo_accounts):
    response = client.post(reverse("accounts:quick_sign_in", args=["SUPERUSER"]))

    assert response.status_code in (404, 422)
    assert "_auth_user_id" not in client.session


@ENABLED
def test_a_deactivated_demonstration_account_is_refused(client, demo_accounts):
    """Deactivation ends access by every route (MVP FR-026), and a convenience route is not
    an exception to that."""
    account = demo_accounts[User.Role.AGENT]
    account.is_active = False
    account.save(update_fields=["is_active"])

    response = quick_sign_in(client, User.Role.AGENT)

    assert response.status_code in (403, 404, 422)
    assert "_auth_user_id" not in client.session


@ENABLED
def test_it_refuses_a_get(client, demo_accounts):
    """Signing in is a state change. A link that a browser or a crawler can follow is not."""
    response = client.get(reverse("accounts:quick_sign_in", args=[User.Role.AGENT]))

    assert response.status_code == 405
    assert "_auth_user_id" not in client.session


@ENABLED
def test_the_customer_facing_screens_are_offered(client, demo_accounts):
    """A customer has no account to sign into — visitors are anonymous until the portal phase
    — so "test as a customer" is a link, not a login."""
    body = client.get(reverse("accounts:sign_in")).content.decode()

    assert reverse("intake:form") in body
    assert reverse("chat:widget") in body
