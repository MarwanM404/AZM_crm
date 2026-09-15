"""
T012. One address is either a member of staff or a customer, never both (FR-032).

The two tables are separate by design, so nothing stops the same address appearing in both
unless something is asked to stop it. What goes wrong is not dramatic: an agent registers on
the portal to see what customers see, and now one address has two passwords, two sessions and
two sets of rights, and an auditor reading the log cannot tell which of them acted.
"""

import pytest

from apps.accounts.models import User
from apps.portal.models import AddressAlreadyInUse, CustomerAccount

pytestmark = pytest.mark.django_db


def test_a_staff_address_cannot_register_as_a_customer(agent):
    with pytest.raises(AddressAlreadyInUse):
        CustomerAccount.objects.create_account(email=agent.email, password="x" * 20)


def test_the_check_ignores_case(agent):
    """Addresses are case-insensitive in practice, and `Agent@Example.com` is the same
    mailbox. A check that compares exactly is a check that can be walked around with a shift
    key."""
    with pytest.raises(AddressAlreadyInUse):
        CustomerAccount.objects.create_account(email=agent.email.upper(), password="x" * 20)


def test_a_customer_address_cannot_become_staff(customer, department, branch):
    with pytest.raises(AddressAlreadyInUse):
        User.objects.create_user(
            email=customer.email,
            password="x" * 20,
            full_name="Somebody",
            department=department,
            branch=branch,
        )


def test_an_unrelated_address_is_unaffected(agent):
    """So the rule cannot be satisfied by refusing every registration."""
    account = CustomerAccount.objects.create_account(email="nobody@example.com", password="x" * 20)

    assert account.pk
