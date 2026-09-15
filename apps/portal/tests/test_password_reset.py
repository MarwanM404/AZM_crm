"""
T077-T080. Recovering a forgotten password (FR-007, FR-011, FR-012).

The second most attacked screen in any product that has one, and the one where getting the
disclosure rule wrong is most tempting: "no account with that address" is genuinely helpful to
somebody who mistyped, and it is also a way to walk a list of addresses and learn which of them
bank with us. The screen says the same thing either way, and the person who owns the address
finds out by receiving a message — or by not receiving one.

The session rule (FR-012) is the part that is usually missed. A reset that changes the password
and leaves the old sessions alive has done nothing about the person who is already inside,
which is the case a reset most often exists for.
"""

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from apps.portal.auth import CUSTOMER_SESSION_KEY
from apps.portal.models import CustomerToken
from apps.portal.tests.identity import comparable

pytestmark = pytest.mark.django_db

OLD_PASSWORD = "a-long-enough-passphrase-42"
NEW_PASSWORD = "a-different-long-passphrase-77"


def ask_for_reset(client, email):
    return client.post(reverse("portal:reset"), {"email": email})


def link_from(message):
    """The reset link lives under /new-password/, not /reset/.

    Deliberately: `reset/<value>/` would have matched `reset/sent/` with value="sent", the
    same collision that made confirm/resend/ answer "this link no longer works". The path is
    reversed rather than spelled out here so the test cannot drift from the route.
    """
    prefix = reverse("portal:reset_confirm", args=["x"]).rsplit("x/", 1)[0]

    for word in message.body.split():
        if prefix in word:
            return word.rstrip(".,")
    raise AssertionError(f"No reset link in:\n{message.body}")


@pytest.fixture
def reset_link(client, customer):
    mail.outbox.clear()
    ask_for_reset(client, customer.email)
    return link_from(mail.outbox[0])


def test_a_message_is_sent_to_the_address(client, customer):
    mail.outbox.clear()

    ask_for_reset(client, customer.email)

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [customer.email]


def test_the_link_lets_them_choose_a_new_password(client, customer, reset_link):
    client.post(reset_link, {"password": NEW_PASSWORD})

    customer.refresh_from_db()
    assert customer.check_password(NEW_PASSWORD)


def test_an_unknown_address_answers_identically(client, customer):
    """T077, FR-007, scenario 2."""
    known = ask_for_reset(client, customer.email)
    unknown = ask_for_reset(client, "nobody@example.com")

    assert known.status_code == unknown.status_code
    assert comparable(known, customer.email) == comparable(unknown, "nobody@example.com")


def test_an_unknown_address_sends_nothing(client):
    """The silence is the whole mechanism: the person who owns the address learns what
    happened, and the person at the screen learns nothing at all."""
    mail.outbox.clear()

    ask_for_reset(client, "nobody@example.com")

    assert mail.outbox == []


def test_a_staff_address_answers_identically_too(client, agent, customer):
    """A member of staff has no portal account and no portal password. The screen must not
    become a way to ask which addresses belong to the organization."""
    mail.outbox.clear()
    known = ask_for_reset(client, customer.email)
    staff = ask_for_reset(client, agent.email)

    assert comparable(known, customer.email) == comparable(staff, agent.email)
    assert [m.to for m in mail.outbox] == [[customer.email]]


# --- single use and expiry (T078, scenarios 3 and 4) ---


def test_a_used_link_stops_working(client, customer, reset_link):
    client.post(reset_link, {"password": NEW_PASSWORD})

    client.post(reset_link, {"password": "a-third-long-passphrase-99"})

    customer.refresh_from_db()
    assert customer.check_password(NEW_PASSWORD)


def test_an_expired_link_does_not_work(client, customer, reset_link):
    token = CustomerToken.objects.get(purpose=CustomerToken.Purpose.RESET)
    token.expires_at = timezone.now() - timezone.timedelta(seconds=1)
    token.save(update_fields=["expires_at"])

    client.post(reset_link, {"password": NEW_PASSWORD})

    customer.refresh_from_db()
    assert customer.check_password(OLD_PASSWORD)


def test_an_expired_link_offers_another(client, customer, reset_link):
    """A dead end here is a customer who cannot get into their account and has nobody to
    ask — which is the support request this whole story exists to prevent."""
    token = CustomerToken.objects.get(purpose=CustomerToken.Purpose.RESET)
    token.expires_at = timezone.now() - timezone.timedelta(seconds=1)
    token.save(update_fields=["expires_at"])

    body = client.get(reset_link, follow=True).content.decode()

    assert reverse("portal:reset") in body


def test_a_confirmation_link_cannot_set_a_password(client, customer):
    """Purposes are separate, asserted through the view. A confirmation link goes to an
    address somebody has just typed into a public form; if it could also set a password,
    registering a stranger's address would be enough to take it."""
    from apps.portal.services import tokens

    value, _ = tokens.issue(customer, CustomerToken.Purpose.CONFIRMATION)

    client.post(reverse("portal:reset_confirm", args=[value]), {"password": NEW_PASSWORD})

    customer.refresh_from_db()
    assert customer.check_password(OLD_PASSWORD)


# --- what completing a reset does (T079, scenario 5) ---


def test_the_previous_password_stops_working(client, customer, reset_link):
    """Signed out first, because completing a reset signs them in — checking the session key
    without that asserts nothing about the old password at all."""
    client.post(reset_link, {"password": NEW_PASSWORD})
    client.post(reverse("portal:sign_out"))

    client.post(reverse("portal:sign_in"), {"email": customer.email, "password": OLD_PASSWORD})

    assert CUSTOMER_SESSION_KEY not in client.session


def test_other_sessions_end(client, customer, reset_link):
    """FR-012, and the reason a reset exists at all.

    The case is somebody else signed in on another machine. Changing the password and leaving
    their session alive does nothing about the only person the reset was aimed at.
    """
    from django.test import Client

    elsewhere = Client()
    elsewhere.post(reverse("portal:sign_in"), {"email": customer.email, "password": OLD_PASSWORD})
    assert elsewhere.get(reverse("portal:home")).status_code == 200, "setup: not signed in"

    client.post(reset_link, {"password": NEW_PASSWORD})

    assert (
        elsewhere.get(reverse("portal:home")).status_code != 200
    ), "A session opened with the old password survived the reset."


def test_the_session_that_did_the_reset_still_works(client, customer, reset_link):
    """So the rule cannot be satisfied by ending every session including this one, which
    would drop somebody at a sign-in page seconds after proving who they are."""
    client.post(reset_link, {"password": NEW_PASSWORD}, follow=True)

    assert client.get(reverse("portal:home")).status_code == 200


def test_outstanding_reset_links_are_burned(client, customer, reset_link):
    """A second link still sitting in a mailbox is a second key to a lock that was just
    changed, held by somebody who believes they are the only one with one."""
    mail.outbox.clear()
    ask_for_reset(client, customer.email)
    second = link_from(mail.outbox[0])

    client.post(reset_link, {"password": NEW_PASSWORD})
    client.post(second, {"password": "a-third-long-passphrase-99"})

    customer.refresh_from_db()
    assert customer.check_password(NEW_PASSWORD)


# --- the new password is held to the same standard (T080) ---


def test_a_weak_new_password_is_refused(client, customer, reset_link):
    response = client.post(reset_link, {"password": "password"})

    customer.refresh_from_db()
    assert customer.check_password(OLD_PASSWORD)
    assert response.context["form"].errors.get("password")


def test_a_refused_attempt_does_not_burn_the_link(client, customer, reset_link):
    """Otherwise a typo costs them the link and they start again from the beginning — for a
    person who is, by definition, already locked out and already frustrated."""
    client.post(reset_link, {"password": "password"})

    client.post(reset_link, {"password": NEW_PASSWORD})

    customer.refresh_from_db()
    assert customer.check_password(NEW_PASSWORD)


def test_a_deactivated_account_cannot_be_reset(client, customer):
    mail.outbox.clear()
    customer.is_active = False
    customer.save(update_fields=["is_active"])

    ask_for_reset(client, customer.email)

    assert mail.outbox == []


def test_an_unconfirmed_account_is_not_offered_a_reset(client, unconfirmed_customer):
    """Resetting the password of an address nobody has proved they own would let anybody who
    registered a stranger's address wait for the stranger to reset it, and inherit the
    account. Confirming is the way in for an unconfirmed account."""
    mail.outbox.clear()

    ask_for_reset(client, unconfirmed_customer.email)

    assert mail.outbox == []
