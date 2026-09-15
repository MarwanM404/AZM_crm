"""
T030. Signing in to the portal (FR-002, scenario 3).

The one deliberate disclosure in this feature is here. Everywhere else the answer is the same
whether or not an address is known; on sign-in, somebody holding the correct password for an
unconfirmed account is told the address is unconfirmed rather than that the password is wrong.

That is a considered trade, not an oversight. To reach the message at all you must already
have the password, so the only person who sees it is overwhelmingly the person who set it
minutes ago. Telling them "wrong password" instead sends them to the reset flow — another
email, for a problem the first email already solved — and they end up reporting the portal as
broken.
"""

import pytest
from django.urls import reverse

from apps.portal.auth import CUSTOMER_SESSION_KEY
from apps.portal.models import CustomerAccount

pytestmark = pytest.mark.django_db

GOOD_PASSWORD = "a-long-enough-passphrase-42"


def sign_in(client, email, password=GOOD_PASSWORD):
    return client.post(reverse("portal:sign_in"), {"email": email, "password": password})


def _without_the_address(response, address):
    """The page with the submitted address and the CSRF token masked out.

    Both differ between any two responses and neither discloses anything: the address is what
    the reader typed, and the token is fresh by design. Written first as a plain byte
    comparison, which failed on the CSRF token — the assertion was comparing randomness and
    would have been red whatever the code did.
    """
    from apps.portal.tests.identity import comparable

    return comparable(response, address)


def test_a_confirmed_customer_can_sign_in(client, customer):
    sign_in(client, customer.email)

    assert client.session[CUSTOMER_SESSION_KEY] == customer.pk


def test_the_wrong_password_does_not(client, customer):
    sign_in(client, customer.email, "not-the-password")

    assert CUSTOMER_SESSION_KEY not in client.session


def test_an_unknown_address_does_not(client):
    sign_in(client, "nobody@example.com")

    assert CUSTOMER_SESSION_KEY not in client.session


def test_an_unconfirmed_account_is_told_it_is_unconfirmed(client, unconfirmed_customer):
    """Scenario 3."""
    response = sign_in(client, unconfirmed_customer.email)
    body = response.content.decode().lower()

    assert CUSTOMER_SESSION_KEY not in client.session
    assert "confirm" in body, (
        "An unconfirmed account was refused without saying so, which sends the customer to "
        "reset a password that is already correct."
    )


def test_an_unconfirmed_account_is_offered_another_message(client, unconfirmed_customer):
    """Telling somebody what is wrong and not how to fix it is half a message."""
    body = sign_in(client, unconfirmed_customer.email).content.decode()

    assert reverse("portal:resend_confirmation") in body


def test_the_wrong_password_on_an_unconfirmed_account_says_nothing(client, unconfirmed_customer):
    """The boundary of the disclosure above.

    The unconfirmed message is acceptable only because holding the password proves who you
    are. Shown to somebody who does NOT have the password, the same message says "this
    address has an account here", which is the oracle every other screen refuses to be.
    """
    known = sign_in(client, unconfirmed_customer.email, "not-the-password")
    unknown = sign_in(client, "nobody-at-all@example.com", "not-the-password")

    assert known.status_code == unknown.status_code
    assert _without_the_address(known, unconfirmed_customer.email) == _without_the_address(
        unknown, "nobody-at-all@example.com"
    )


def test_a_deactivated_account_cannot_sign_in(client, customer):
    customer.is_active = False
    customer.save(update_fields=["is_active"])

    sign_in(client, customer.email)

    assert CUSTOMER_SESSION_KEY not in client.session


def test_a_deactivated_account_is_not_told_to_confirm(client, customer):
    """It has confirmed. Offering the confirmation flow to somebody who has been deactivated
    is an invitation to keep trying, and an admission that the address is known."""
    customer.is_active = False
    customer.save(update_fields=["is_active"])

    body = sign_in(client, customer.email).content.decode()

    assert reverse("portal:resend_confirmation") not in body


def test_the_address_is_not_case_sensitive(client, customer):
    sign_in(client, customer.email.upper())

    assert client.session[CUSTOMER_SESSION_KEY] == customer.pk


def test_the_session_identifier_changes_on_sign_in(client, customer):
    """Session fixation: an identifier handed out before sign-in must not still be valid
    after it, or anybody who planted one is now signed in as this customer."""
    client.get(reverse("portal:sign_in"))
    before = client.session.session_key

    sign_in(client, customer.email)

    assert client.session.session_key != before


def test_signing_out_ends_the_session(customer_client):
    customer_client.post(reverse("portal:sign_out"))

    assert CUSTOMER_SESSION_KEY not in customer_client.session


def test_signing_out_needs_a_post(customer_client):
    """A GET that a browser, a crawler, or an image tag can follow is not a state change."""
    assert customer_client.get(reverse("portal:sign_out")).status_code == 405


def test_a_staff_password_does_not_work_here(client, agent):
    """The staff credentials are real; they are simply not portal credentials."""
    sign_in(client, agent.email, "agent-password")

    assert CUSTOMER_SESSION_KEY not in client.session


def test_an_unknown_address_costs_about_the_same_as_a_known_one(client, customer):
    """FR-007 in the time domain.

    A sign-in that returns immediately for an unknown address and spends the full password
    hashing cost for a known one is an enumeration oracle measured in milliseconds. The
    margin here is deliberately loose — this asserts the absence of the obvious shortcut, not
    a timing guarantee a shared test runner could not provide.
    """
    import time

    def elapsed(email):
        samples = []
        for _ in range(3):
            start = time.perf_counter()
            sign_in(client, email, "not-the-password")
            samples.append(time.perf_counter() - start)
        return min(samples)

    known = elapsed(customer.email)
    unknown = elapsed("nobody@example.com")

    assert unknown > known / 4, (
        f"An unknown address answered in {unknown:.4f}s against {known:.4f}s for a known one. "
        "The difference is large enough to enumerate accounts with."
    )


def test_registration_makes_an_account_that_can_then_sign_in(client):
    """The whole of User Story 1 end to end, in one test, because the three screens can each
    be correct and still not join up."""
    from django.core import mail

    mail.outbox.clear()
    client.post(
        reverse("portal:register"), {"email": "noura@example.com", "password": GOOD_PASSWORD}
    )
    link = next(w for w in mail.outbox[0].body.split() if "/confirm/" in w).rstrip(".,")
    client.get(link)
    client.post(reverse("portal:sign_out"))

    sign_in(client, "noura@example.com")

    assert (
        client.session[CUSTOMER_SESSION_KEY]
        == CustomerAccount.objects.get(email="noura@example.com").pk
    )
