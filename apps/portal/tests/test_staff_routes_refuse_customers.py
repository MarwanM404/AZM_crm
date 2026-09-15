"""
T007, T008, T010. A customer session reaches no staff route (FR-028, FR-029).

Read the second test in this file before the first one. `test_every_staff_route_refuses_a
_customer` is the obvious check and it is not the one that matters, because it would pass
for the wrong reason: a customer has no department, and a customer with no department sees
nothing anywhere in this product (spec 003, FR-023). It would report the boundary working
whether or not anybody built it.

`test_the_refusal_does_not_depend_on_having_no_scope` removes that. It gives the customer
account every staff-shaped attribute a future change might add — a role, a department, a
branch, an `is_authenticated` that answers True — and asserts every refusal still holds.
What it is really asserting is that a customer never becomes `request.user` at all, which is
the property the separate account model exists to produce (research.md §1).
"""

import pytest
from django.conf import settings
from django.urls import reverse

from apps.portal.models import CustomerAccount
from apps.portal.tests.routes import staff_routes

pytestmark = pytest.mark.django_db

SIGN_IN = reverse(settings.LOGIN_URL)


def assert_refused(response, name, url):
    """Refused means: not served, and not redirected anywhere except the staff sign-in page.

    A redirect is the correct refusal here rather than a 403. To the staff side of this
    product a customer simply is not signed in, so they meet the same deny-by-default wall an
    anonymous visitor meets — which is the design working, not a gap in it.
    """
    assert response.status_code != 200, (
        f"{name} ({url}) served a customer session a page. Staff routes must refuse "
        "customers outright."
    )
    if response.status_code in (301, 302):
        destination = response["Location"].split("?")[0]
        assert destination == SIGN_IN, (
            f"{name} ({url}) redirected a customer to {destination}, not to the sign-in page. "
            "A redirect further into the staff application is not a refusal."
        )


def test_there_are_staff_routes_to_refuse():
    """The guard on the two tests below. Both iterate a discovered set, and a discovery that
    silently returned nothing would make them pass without testing anything — which is the
    exact failure mode this project keeps meeting."""
    routes = staff_routes()

    assert len(routes) > 30, (
        f"Only {len(routes)} staff routes were discovered. The enumeration in "
        "apps/portal/tests/routes.py has probably stopped working, and the refusal tests "
        "below are passing vacuously."
    )


def test_every_staff_route_refuses_a_customer(customer_client):
    """FR-029."""
    for name, url in staff_routes().items():
        assert_refused(customer_client.get(url), name, url)


def test_the_refusal_does_not_depend_on_having_no_scope(
    customer_client, department, branch, monkeypatch
):
    """FR-028, and the reason this feature has its own account model.

    Every attribute below is attached to the *class*, so it survives the account being
    re-read from the database on each request — which is what makes this a real test rather
    than a test of Django's instance caching.
    """
    monkeypatch.setattr(CustomerAccount, "role", "ADMINISTRATOR", raising=False)
    monkeypatch.setattr(CustomerAccount, "department", department, raising=False)
    monkeypatch.setattr(CustomerAccount, "branch", branch, raising=False)
    monkeypatch.setattr(CustomerAccount, "is_staff", True, raising=False)
    monkeypatch.setattr(CustomerAccount, "is_superuser", True, raising=False)
    monkeypatch.setattr(CustomerAccount, "is_authenticated", True, raising=False)

    for name, url in staff_routes().items():
        assert_refused(customer_client.get(url), name, url)


def test_a_customer_is_not_request_user(customer_client):
    """The mechanism behind both tests above, asserted directly so that a failure says what
    broke rather than only that something did."""
    response = customer_client.get(reverse("tickets:queue"))

    assert response.wsgi_request.user.is_authenticated is False
    assert not isinstance(response.wsgi_request.user, CustomerAccount)


def test_a_customer_cannot_recover_a_scope(customer_client):
    """T010. Spec 003 added a self-service route for an administrator locked out by having no
    department. A customer also has no department, and the two situations must not be
    confused: one is an administrator who needs their scope back, the other is somebody who
    must never have one."""
    url = reverse("administration:own_scope")

    assert_refused(customer_client.get(url), "administration:own_scope", url)
    assert_refused(customer_client.post(url, {}), "administration:own_scope", url)


def test_a_customer_cannot_use_the_staff_sign_in(client, customer):
    """The address and password are real; they are simply not staff credentials. If the staff
    form authenticated against CustomerAccount, everything above would be irrelevant."""
    client.post(
        reverse("accounts:sign_in"),
        {"username": customer.email, "password": "a-long-enough-passphrase-42"},
    )

    assert "_auth_user_id" not in client.session
