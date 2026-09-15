"""
The portal reads the customer's stored language (MVP FR-031, FR-033).

Written after the defect, not before it: thirty-nine tests passed over an Arabic customer
being served an English page, because every one of them asserted on status codes and on
content that reads the same in both languages. It was found by taking a screenshot.

The cause is worth remembering rather than just fixing. `UserLanguageMiddleware` activates
`request.user.language`, and the portal's whole design is that a customer is never
`request.user` — so every convenience the staff side gets from that middleware has to be
rebuilt here, and the ones that are missed fail silently and look fine to a reader who speaks
English.
"""

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_an_arabic_customer_gets_an_arabic_page(client, customer):
    from apps.portal.tests.sessions import sign_in as start_session

    customer.language = "ar"
    customer.save(update_fields=["language"])

    start_session(client, customer)

    response = client.get(reverse("portal:home"))
    body = response.content.decode()

    assert response.context["LANGUAGE_CODE"] == "ar"
    assert 'dir="rtl"' in body
    assert "طلبات الدعم" in body, "An Arabic customer was served an English page."


def test_an_english_customer_gets_an_english_page(client, customer):
    """The other half. A middleware hard-wired to Arabic would pass the test above."""

    from apps.portal.tests.sessions import sign_in as start_session

    customer.language = "en"
    customer.save(update_fields=["language"])

    start_session(client, customer)

    body = client.get(reverse("portal:home")).content.decode()

    assert 'dir="ltr"' in body
    assert "Your support requests" in body


def test_the_language_does_not_leak_to_the_next_request(customer_client, customer, client):
    """`translation.activate` sets the language for the THREAD, not the request.

    Without the restore in the middleware, one Arabic customer's request leaves the whole
    worker in Arabic — and the next visitor to any page, staff or public, gets Arabic
    regardless of what they asked for.
    """
    from django.utils import translation

    customer.language = "ar"
    customer.save(update_fields=["language"])
    customer_client.get(reverse("portal:home"))

    assert translation.get_language() != "ar" or translation.get_language() == "en"

    # The observable consequence, which is what actually matters.
    body = client.get(reverse("intake:form"), HTTP_ACCEPT_LANGUAGE="en").content.decode()
    assert 'dir="ltr"' in body


def test_the_switch_actually_switches(customer_client, customer):
    """The control on every portal screen does what it appears to do.

    Written after clicking it in a browser and watching nothing happen. The switch posted to
    the anonymous route, which sets a cookie; the middleware then activated the account's
    stored language over the top of it. Every test passed, because no test clicked anything.
    """
    customer.language = "ar"
    customer.save(update_fields=["language"])

    response = customer_client.post(
        reverse("portal:language"),
        {"language": "en", "next": reverse("portal:home")},
        follow=True,
    )
    body = response.content.decode()

    customer.refresh_from_db()
    assert customer.language == "en", "The choice was not remembered on the account."
    assert "Your support requests" in body, "The page came back in the old language."


def test_the_switch_refuses_a_language_that_does_not_exist(customer_client, customer):
    response = customer_client.post(reverse("portal:language"), {"language": "fr"})

    assert response.status_code == 400
    customer.refresh_from_db()
    assert customer.language == "ar"


def test_the_switch_will_not_redirect_off_this_site(customer_client):
    """`next` comes from the request. Unchecked, this is an open redirect on a page anybody
    who can register can reach."""
    response = customer_client.post(
        reverse("portal:language"), {"language": "en", "next": "https://example.net/phish"}
    )

    assert response["Location"] == reverse("portal:home")


def test_the_switch_needs_a_customer(client):
    """It writes to an account, so there must be one.

    Refused today by the deny-by-default wall rather than by `customer_required`, because
    the route is not in LOGIN_EXEMPT_URL_NAMES — so an anonymous caller is redirected before
    the view is reached. Both guards are wanted: the wall is what happens to be first, and
    the decorator is what still refuses if the route is ever exempted for another reason.
    """
    response = client.post(reverse("portal:language"), {"language": "en"})

    assert response.status_code in (302, 404)
    if response.status_code == 302:
        assert response["Location"].startswith(reverse("accounts:sign_in"))
