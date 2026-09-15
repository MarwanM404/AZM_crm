"""
T081-T082. Repeated failures lock the account (FR-011).

The lockout, not the rate limit, is what actually stops password guessing here. The rate limit
lives in the cache and fails OPEN by design (research.md #6) — a Redis outage must not turn
away genuine customers — so while Redis is down the limiter is simply not there. This is the
defence that does not depend on it, which is why it is stored on the account rather than in
the cache.

It is also deliberately a lockout with an end. This product has no self-service unlock for
staff and no support queue a locked-out customer could reach, so a lock that needs a human to
release it is a customer who cannot get help — and the person most likely to be locked out is
the legitimate owner having a bad morning.
"""

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from apps.portal.auth import CUSTOMER_SESSION_KEY
from apps.portal.tests.identity import comparable

pytestmark = pytest.mark.django_db

PASSWORD = "a-long-enough-passphrase-42"


@pytest.fixture(autouse=True)
def no_rate_limit(settings):
    """The limiter would refuse these attempts long before the lockout counted them, and this
    file is about the lockout. Raised rather than removed, so the view is exercised as it
    really runs."""
    settings.PORTAL_SIGN_IN_RATE_PER_ADDRESS = "10000/h"
    settings.PORTAL_SIGN_IN_RATE_PER_SOURCE = "10000/h"


def sign_in(client, email, password):
    return client.post(reverse("portal:sign_in"), {"email": email, "password": password})


def fail(client, customer, times):
    for _ in range(times):
        sign_in(client, customer.email, "not-the-password")


def test_repeated_failures_lock_the_account(client, customer, settings):
    settings.PORTAL_LOCKOUT_THRESHOLD = 3

    fail(client, customer, 3)
    sign_in(client, customer.email, PASSWORD)

    assert (
        CUSTOMER_SESSION_KEY not in client.session
    ), "The correct password still worked after the account was locked."


def test_the_correct_password_works_before_the_threshold(client, customer, settings):
    """So the rule cannot be satisfied by refusing everybody. One mistyped password must not
    cost somebody fifteen minutes."""
    settings.PORTAL_LOCKOUT_THRESHOLD = 3

    fail(client, customer, 2)
    sign_in(client, customer.email, PASSWORD)

    assert client.session[CUSTOMER_SESSION_KEY] == customer.pk


def test_a_success_clears_the_count(client, customer, settings):
    """Consecutive failures, not failures ever. Without this the counter accumulates over
    months and locks somebody out on a Tuesday for typos spread across a year."""
    settings.PORTAL_LOCKOUT_THRESHOLD = 3

    fail(client, customer, 2)
    sign_in(client, customer.email, PASSWORD)
    client.post(reverse("portal:sign_out"))
    fail(client, customer, 2)
    sign_in(client, customer.email, PASSWORD)

    assert client.session[CUSTOMER_SESSION_KEY] == customer.pk


def test_the_lock_ends_by_itself(client, customer, settings):
    settings.PORTAL_LOCKOUT_THRESHOLD = 3
    fail(client, customer, 3)

    customer.refresh_from_db()
    customer.locked_until = timezone.now() - timezone.timedelta(seconds=1)
    customer.save(update_fields=["locked_until"])

    sign_in(client, customer.email, PASSWORD)

    assert client.session[CUSTOMER_SESSION_KEY] == customer.pk


def test_the_owner_is_told(client, customer, settings):
    """FR-011, scenario 7. The owner of the address is the only person who can act on it —
    and if the attempts are not theirs, this is how they find out."""
    settings.PORTAL_LOCKOUT_THRESHOLD = 3
    mail.outbox.clear()

    fail(client, customer, 3)

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [customer.email]


def test_the_owner_is_told_once_not_on_every_further_attempt(client, customer, settings):
    """An attacker who keeps going must not be able to use this to send the owner a thousand
    emails from our mail server."""
    settings.PORTAL_LOCKOUT_THRESHOLD = 3
    mail.outbox.clear()

    fail(client, customer, 12)

    assert len(mail.outbox) == 1


def test_the_notice_carries_no_link_that_signs_anybody_in(client, customer, settings):
    settings.PORTAL_LOCKOUT_THRESHOLD = 3
    mail.outbox.clear()

    fail(client, customer, 3)

    assert "not-the-password" not in mail.outbox[0].body


def test_a_lockout_does_not_reveal_that_the_address_is_known(client, customer, settings):
    """T082. The screen has spent this whole feature refusing to say whether an address has an
    account; a lockout message saying "this account is locked" would give it away on the one
    screen an attacker is already hammering."""
    settings.PORTAL_LOCKOUT_THRESHOLD = 3

    fail(client, customer, 3)
    locked = sign_in(client, customer.email, PASSWORD)
    unknown = sign_in(client, "nobody@example.com", PASSWORD)

    assert locked.status_code == unknown.status_code
    assert comparable(locked, customer.email) == comparable(unknown, "nobody@example.com")


def test_locking_one_account_does_not_lock_another(client, customer, settings):
    settings.PORTAL_LOCKOUT_THRESHOLD = 3
    from apps.portal.models import CustomerAccount

    other = CustomerAccount.objects.create_account(email="other@example.com", password=PASSWORD)
    other.confirm()

    fail(client, customer, 3)
    sign_in(client, other.email, PASSWORD)

    assert client.session[CUSTOMER_SESSION_KEY] == other.pk


def test_a_reset_unlocks_the_account(client, customer, settings):
    """Somebody who proves they read the mailbox has answered the question the lock was
    asking. Leaving them locked out after a successful reset is a dead end with no way
    through — they have done the only thing the product offered them."""
    settings.PORTAL_LOCKOUT_THRESHOLD = 3
    fail(client, customer, 3)

    mail.outbox.clear()
    client.post(reverse("portal:reset"), {"email": customer.email})
    from apps.portal.tests.test_password_reset import link_from

    link = link_from(mail.outbox[0])
    client.post(link, {"password": "a-different-long-passphrase-77"})
    client.post(reverse("portal:sign_out"))

    sign_in(client, customer.email, "a-different-long-passphrase-77")

    assert client.session[CUSTOMER_SESSION_KEY] == customer.pk


def test_the_lockout_survives_the_cache_being_empty(client, customer, settings):
    """The property the whole design rests on: this is stored on the account, so it is still
    there when the rate limiter is not."""
    from django.core.cache import cache

    settings.PORTAL_LOCKOUT_THRESHOLD = 3
    fail(client, customer, 3)

    cache.clear()

    sign_in(client, customer.email, PASSWORD)
    assert CUSTOMER_SESSION_KEY not in client.session
