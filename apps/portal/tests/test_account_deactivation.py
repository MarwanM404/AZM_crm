"""
T011. Deactivation ends access by every route (FR-031, echoing MVP FR-026).

The check has to happen per request rather than at sign-in. A customer deactivated while
holding a valid session is the case that matters — somebody abusing the portal is deactivated
precisely while they are using it, and a check that only runs at sign-in leaves them working
until they choose to sign out.
"""

import pytest

from apps.portal.tests.routes import portal_routes

pytestmark = pytest.mark.django_db


def behind_sign_in():
    """The portal routes that require a customer.

    Registration, sign-in and confirmation are public by design and serve everybody 200,
    including a customer who has just been deactivated — which is correct and is not what
    this file is about. Derived from LOGIN_EXEMPT_URL_NAMES rather than listed, so a public
    route added later is excluded here on the day it is exempted there rather than on the day
    this test starts failing for a reason nobody expects.
    """
    from django.conf import settings

    return {
        name: url
        for name, url in portal_routes().items()
        if name not in settings.LOGIN_EXEMPT_URL_NAMES
    }


def test_a_deactivated_customer_cannot_sign_in(client, customer):
    from apps.portal import auth

    customer.is_active = False
    customer.save(update_fields=["is_active"])

    assert auth.authenticate_customer(customer.email, "a-long-enough-passphrase-42") is None


def test_deactivation_ends_a_session_already_in_progress(customer_client, customer):
    customer.is_active = False
    customer.save(update_fields=["is_active"])

    for name, url in behind_sign_in().items():
        assert customer_client.get(url).status_code != 200, (
            f"{name} ({url}) still served a deactivated customer. The check must run on each "
            "request, not once at sign-in."
        )


def test_an_active_customer_is_still_served(customer_client):
    """The other half, so that a decorator which refuses everybody cannot pass the test
    above. A check that only ever says no is indistinguishable from a broken screen."""
    served = [
        url for url in portal_routes().values() if customer_client.get(url).status_code == 200
    ]

    assert served, "A confirmed, active customer was served no portal page at all."
