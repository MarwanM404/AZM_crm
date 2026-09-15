"""
T006. A customer account has no staff shape at all (FR-028).

The assertion is about *absence of the fields*, not about their values being empty, and the
difference is the whole point. An account with `department = None` is one assignment away
from being scoped staff, and that assignment can arrive from a data migration, an admin
action, a fixture, or a well-meaning `setattr` in a future feature. A model with no such
field cannot be assigned one, and a staff query filtering on `department` cannot match it.

research.md §1 records why this is structural rather than checked: the login middleware's
rule is "authenticated -> let through", and `role` defaults to AGENT. On a `User`, a customer
is an agent minus a department.
"""

import pytest
from django.db import IntegrityError

from apps.portal.models import CustomerAccount

STAFF_FIELDS = ["role", "department", "branch", "is_staff", "is_superuser"]


def test_it_has_no_staff_fields():
    present = {f.name for f in CustomerAccount._meta.get_fields()}

    for field in STAFF_FIELDS:
        assert field not in present, (
            f"CustomerAccount has a `{field}` field. It must not exist at all: a field that "
            "exists can be populated, and a customer with a department is a customer inside "
            "the staff authorization model."
        )


def test_it_is_not_the_staff_user_model():
    """Different table, different model, no inheritance. If a customer were a `User`
    subclass, every `User.objects` query in the product would return customers."""
    from apps.accounts.models import User

    assert not issubclass(CustomerAccount, User)
    assert CustomerAccount._meta.db_table != User._meta.db_table


def test_no_staff_query_can_return_a_customer(db, department, branch):
    """The property the two facts above exist to produce."""
    from apps.accounts.models import User

    CustomerAccount.objects.create_account(email="c@example.com", password="x" * 20)

    assert not User.objects.filter(email="c@example.com").exists()


def test_nothing_in_the_portal_assigns_a_staff_attribute():
    """A source sweep, because the model check above only covers the shape declared today.

    `setattr(account, "department", d)` on a model with no such field succeeds silently in
    Python — it just does not persist. That is enough to fool a permission check written as
    `getattr(account, "department", None)`, so the portal must not contain the assignment
    even though the model would not store it.
    """
    from pathlib import Path

    portal = Path(__file__).resolve().parent.parent
    offenders = []
    for source in portal.rglob("*.py"):
        if "tests" in source.parts:
            continue
        for number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for field in ("role", "department", "branch", "is_staff", "is_superuser"):
                if f".{field} =" in stripped or f'"{field}"' in stripped and "=" in stripped:
                    offenders.append(f"{source.relative_to(portal)}:{number}: {stripped}")

    assert not offenders, "The portal assigns a staff attribute:\n" + "\n".join(offenders)


@pytest.mark.django_db
def test_an_address_is_stored_once():
    CustomerAccount.objects.create_account(email="dup@example.com", password="x" * 20)

    # Named rather than bare: `pytest.raises(Exception)` would also pass on a typo in this
    # test, which is a test that passes when nothing works.
    with pytest.raises(IntegrityError):
        CustomerAccount.objects.create_account(email="dup@example.com", password="y" * 20)


@pytest.mark.django_db
def test_the_password_cannot_be_read_back():
    account = CustomerAccount.objects.create_account(
        email="hash@example.com", password="a-real-passphrase-42"
    )

    assert "a-real-passphrase-42" not in account.password
    assert account.check_password("a-real-passphrase-42")
    assert not account.check_password("something else")


@pytest.mark.django_db
def test_an_account_starts_unconfirmed():
    account = CustomerAccount.objects.create_account(email="new@example.com", password="x" * 20)

    assert account.email_confirmed_at is None
    assert not account.is_confirmed
