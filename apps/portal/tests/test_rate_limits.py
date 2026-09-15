"""
T031. Limits on the public screens (FR-010).

Two limits per screen, per address and per source, because they stop different things. Per
address stops one account being ground down; per source stops one machine working through a
list of addresses. A screen carrying only one of them looks rate-limited and is not.

The cache is cleared between tests by the autouse fixture in conftest.py. Without it these
pass and fail by ordering, which this project has been caught by before — and the symptom is
the worst kind: a suite that is green on a rerun.
"""

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db

GOOD_PASSWORD = "a-long-enough-passphrase-42"


def attempts(client, url, payload, count):
    return [client.post(url, payload) for _ in range(count)]


def refused(response):
    """Refused by the limiter rather than by the form.

    429 is the honest code. 200 with a message is acceptable too, since the house pattern
    fails open and redisplays — what is NOT acceptable is the attempt succeeding.
    """
    return response.status_code == 429 or b"too many" in response.content.lower()


def test_registration_is_limited_per_address(client, settings):
    settings.PORTAL_REGISTER_RATE_PER_ADDRESS = "3/h"
    settings.PORTAL_REGISTER_RATE_PER_SOURCE = "1000/h"
    url = reverse("portal:register")

    responses = attempts(client, url, {"email": "a@example.com", "password": GOOD_PASSWORD}, 6)

    assert any(refused(r) for r in responses), "Six registrations of one address, none refused."


def test_registration_is_limited_per_source(client, settings):
    """The limit that matters for enumeration. Per-address alone is no protection at all
    against somebody working down a list, because every attempt uses a different address."""
    settings.PORTAL_REGISTER_RATE_PER_ADDRESS = "1000/h"
    settings.PORTAL_REGISTER_RATE_PER_SOURCE = "3/h"
    url = reverse("portal:register")

    responses = [
        client.post(url, {"email": f"person{n}@example.com", "password": GOOD_PASSWORD})
        for n in range(6)
    ]

    assert any(refused(r) for r in responses), (
        "Six registrations of six different addresses from one source, none refused. The "
        "per-address limit does not see this at all."
    )


def test_sign_in_is_limited(client, customer, settings):
    settings.PORTAL_SIGN_IN_RATE_PER_ADDRESS = "3/h"
    url = reverse("portal:sign_in")

    responses = attempts(client, url, {"email": customer.email, "password": "wrong"}, 6)

    assert any(refused(r) for r in responses)


def test_asking_for_another_confirmation_is_limited(client, unconfirmed_customer, settings):
    """This screen sends mail to an address on request. Unlimited, it is a way to send
    somebody a hundred emails using our mail server and our reputation."""
    settings.PORTAL_CONFIRM_RESEND_RATE_PER_ADDRESS = "3/h"
    url = reverse("portal:resend_confirmation")

    responses = attempts(client, url, {"email": unconfirmed_customer.email}, 6)

    assert any(refused(r) for r in responses)


def test_a_refusal_says_when_to_try_again(client, settings):
    """A limit that refuses without saying for how long teaches people to keep retrying,
    which is the behaviour it exists to stop."""
    settings.PORTAL_REGISTER_RATE_PER_ADDRESS = "1/h"
    url = reverse("portal:register")
    payload = {"email": "a@example.com", "password": GOOD_PASSWORD}

    attempts(client, url, payload, 2)
    body = client.post(url, payload).content.decode().lower()

    assert (
        "hour" in body or "later" in body or "minute" in body
    ), "The refusal does not tell the customer when they may try again."


def test_a_refusal_does_not_reveal_whether_the_address_is_known(client, customer, settings):
    """The limiter must not become the oracle the screens refuse to be."""
    settings.PORTAL_REGISTER_RATE_PER_SOURCE = "1/h"
    url = reverse("portal:register")

    client.post(url, {"email": "warmup@example.com", "password": GOOD_PASSWORD})
    known = client.post(url, {"email": customer.email, "password": GOOD_PASSWORD})
    unknown = client.post(url, {"email": "nobody@example.com", "password": GOOD_PASSWORD})

    from apps.portal.tests.identity import comparable

    assert known.status_code == unknown.status_code
    assert comparable(known, customer.email) == comparable(unknown, "nobody@example.com")


def test_a_limited_attempt_writes_nothing(client, settings):
    """Refusing after the account exists is not refusing."""
    from apps.portal.models import CustomerAccount

    settings.PORTAL_REGISTER_RATE_PER_SOURCE = "1/h"
    url = reverse("portal:register")

    client.post(url, {"email": "first@example.com", "password": GOOD_PASSWORD})
    client.post(url, {"email": "second@example.com", "password": GOOD_PASSWORD})

    assert not CustomerAccount.objects.filter(email="second@example.com").exists()


def test_the_limits_are_settings_not_literals():
    """FR-010 requires both numbers to be tunable without a release. A rate written into a
    decorator is a rate that needs a deployment to change, on the day it is being abused."""
    from pathlib import Path

    views = (Path(__file__).resolve().parent.parent / "views.py").read_text(encoding="utf-8")
    import re

    literals = re.findall(r'rate\s*=\s*["\']\d+/[smhd]["\']', views)

    assert not literals, f"Rate limits hard-coded in views.py: {literals}"


def test_reading_a_page_does_not_use_up_the_limit(client, settings):
    """django-ratelimit counts every method by default, including GET.

    Left at the default, opening the registration screen a few times exhausts the quota and
    the page refuses somebody who has not yet typed anything — and the per-address key is
    meaningless on a GET anyway, because there is no address on the request to key on.

    Found in a browser: a script loading each screen to photograph it was rate-limited out of
    registering.
    """
    settings.PORTAL_REGISTER_RATE_PER_SOURCE = "2/h"
    url = reverse("portal:register")

    for _ in range(6):
        assert client.get(url).status_code == 200, "Reading the page consumed the limit."

    assert client.post(url, {"email": "a@example.com", "password": GOOD_PASSWORD}).status_code in (
        200,
        302,
    ), "The first POST was refused because GETs had already spent the quota."


def test_a_failed_sign_in_still_counts(client, customer, settings):
    """The other direction: limiting POSTs must not turn into limiting only SUCCESSFUL posts.

    Counting only what succeeds would leave password guessing — every attempt of which fails
    — completely unlimited, which is the one thing this limit exists for.
    """
    settings.PORTAL_SIGN_IN_RATE_PER_ADDRESS = "3/h"
    url = reverse("portal:sign_in")

    responses = [client.post(url, {"email": customer.email, "password": "wrong"}) for _ in range(6)]

    assert any(refused(r) for r in responses)
