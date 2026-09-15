"""
Fixtures for the portal's tests.

`customer` and `customer_client` deliberately do not go through Django's `client.force_login`.
That helper sets the *staff* session key, and a customer using it would prove nothing about
the portal's own session — it would prove that Django's session framework works, on a page
the customer is not supposed to have reached.
"""

import pytest

from apps.portal.models import CustomerAccount


@pytest.fixture
def customer(db):
    account = CustomerAccount.objects.create_account(
        email="noura@example.com",
        password="a-long-enough-passphrase-42",
    )
    account.confirm()
    return account


@pytest.fixture
def unconfirmed_customer(db):
    return CustomerAccount.objects.create_account(
        email="unconfirmed@example.com",
        password="a-long-enough-passphrase-42",
    )


@pytest.fixture
def customer_client(client, customer):
    """A test client holding a real portal session.

    Built by writing the session directly rather than by posting the sign-in form, because
    the form does not exist until User Story 1 and because a fixture that depends on a screen
    fails for two different reasons once that screen exists.

    It uses apps.portal.auth's own key rather than a literal, so that renaming the key breaks
    this in one place instead of leaving every refusal test silently signed out — which would
    make them all pass.
    """
    from django.conf import settings

    from apps.portal.auth import CUSTOMER_SESSION_KEY

    session = client.session
    session[CUSTOMER_SESSION_KEY] = customer.pk
    session.save()
    client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key
    return client


@pytest.fixture
def customer_contact(db, customer, department, branch):
    """A contact record carrying the same address the customer confirmed.

    Created separately from the account on purpose: nothing links the two in the database,
    and the whole of research.md §2 rests on that. The match happens at read time, by address.
    """
    from apps.customers.services.matching import find_or_create_contact

    contact, _ = find_or_create_contact(
        full_name="Noura Al-Harbi",
        email=customer.email,
        department=department,
        branch=branch,
    )
    return contact


@pytest.fixture
def customer_ticket(db, customer_contact, category, department, branch):
    from apps.tickets.models import Ticket

    return Ticket.objects.create(
        contact=customer_contact,
        organization=customer_contact.organization,
        subject="The delivery never arrived",
        description="We were told it shipped on Tuesday and nothing has come.",
        category=category,
        origin_channel=Ticket.Channel.WEB_FORM,
        department=department,
        branch=branch,
    )
