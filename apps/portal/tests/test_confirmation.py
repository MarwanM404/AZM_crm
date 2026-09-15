"""
T028. Following the confirmation link (FR-002, FR-004).

The link is a GET that changes state, which is normally a mistake. It is correct here because
the only thing that can follow it is a person clicking in their mail client, and mail clients
do not POST. What makes that safe is everything else about the token: it is single use, it
expires, it is unguessable, and it does exactly one thing.
"""

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from apps.portal.models import CustomerAccount, CustomerToken
from apps.portal.services import tokens

pytestmark = pytest.mark.django_db

GOOD_PASSWORD = "a-long-enough-passphrase-42"


@pytest.fixture
def registered(client):
    mail.outbox.clear()
    client.post(
        reverse("portal:register"),
        {"email": "noura@example.com", "password": GOOD_PASSWORD},
    )
    account = CustomerAccount.objects.get(email="noura@example.com")
    return account, _link_from(mail.outbox[0].body)


def _link_from(body):
    for word in body.split():
        if "/confirm/" in word:
            return word.rstrip(".,")
    raise AssertionError(f"No confirmation link in the message:\n{body}")


def test_following_it_proves_the_address(client, registered):
    account, link = registered

    client.get(link)

    account.refresh_from_db()
    assert account.is_confirmed
    assert account.may_use_the_portal


def test_it_signs_the_customer_in(client, registered):
    """Scenario 2 ends "and they can sign in". Signing them in directly is the kinder reading
    and the safe one: whoever followed the link demonstrably reads that mailbox, which is a
    stronger proof than the password they are about to type."""
    _, link = registered

    client.get(link, follow=True)

    from apps.portal.auth import CUSTOMER_SESSION_KEY

    assert CUSTOMER_SESSION_KEY in client.session


def test_it_works_once(client, registered):
    """Scenario 7. A message sits in a mailbox, gets forwarded, gets backed up, gets read on a
    shared machine. Single use is what stops the copy being as good as the original."""
    account, link = registered
    client.get(link)
    client.cookies.clear()

    client.get(link)

    from apps.portal.auth import CUSTOMER_SESSION_KEY

    assert CUSTOMER_SESSION_KEY not in client.session


def test_an_expired_link_does_not_work(client, registered):
    """Scenario 8."""
    account, link = registered
    token = CustomerToken.objects.get(account=account)
    token.expires_at = timezone.now() - timezone.timedelta(seconds=1)
    token.save(update_fields=["expires_at"])

    client.get(link)

    account.refresh_from_db()
    assert not account.is_confirmed


def test_an_expired_link_offers_another_one(client, registered):
    """The second half of scenario 8, and the half that is usually missed. A dead end here is
    an account nobody can ever use and a customer with nobody to ask."""
    account, link = registered
    token = CustomerToken.objects.get(account=account)
    token.expires_at = timezone.now() - timezone.timedelta(seconds=1)
    token.save(update_fields=["expires_at"])

    body = client.get(link, follow=True).content.decode()

    assert reverse("portal:resend_confirmation") in body


def test_another_confirmation_can_be_requested(client, registered):
    account, _ = registered
    mail.outbox.clear()

    client.post(reverse("portal:resend_confirmation"), {"email": account.email})

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [account.email]


def test_asking_again_for_an_unknown_address_says_the_same_thing(client, registered):
    """FR-007 applies here too. A resend screen that answers differently for an unknown
    address is the same oracle as a registration screen that does."""
    account, _ = registered
    known = client.post(reverse("portal:resend_confirmation"), {"email": account.email})
    unknown = client.post(reverse("portal:resend_confirmation"), {"email": "nobody@example.com"})

    assert known.status_code == unknown.status_code
    assert known.content == unknown.content


def test_a_forged_link_does_nothing(client, registered):
    account, _ = registered

    client.get(reverse("portal:confirm", args=["a-value-somebody-made-up"]))

    account.refresh_from_db()
    assert not account.is_confirmed


def test_a_reset_token_cannot_confirm_an_address(client, registered):
    """The purposes are separate, asserted through the view rather than only the service —
    the service could be right and the view could pass the wrong purpose."""
    account, _ = registered
    value, _token = tokens.issue(account, CustomerToken.Purpose.RESET)

    client.get(reverse("portal:confirm", args=[value]))

    account.refresh_from_db()
    assert not account.is_confirmed


def test_confirming_an_already_confirmed_account_is_harmless(client, registered):
    """Somebody clicks the old link a week later. It should not sign them in, and it should
    not look like a fault in the product."""
    account, link = registered
    client.get(link)
    client.cookies.clear()

    response = client.get(link, follow=True)

    account.refresh_from_db()
    assert account.is_confirmed
    assert response.status_code == 200


def test_the_resend_path_is_not_swallowed_by_the_confirm_pattern(client):
    """A regression pin, because this shipped for ten minutes and the symptom was perverse.

    `confirm/<str:value>/` matched `confirm/resend/` with value="resend", so the screen that
    exists to rescue somebody whose link expired answered "this link no longer works".
    """
    from django.urls import resolve

    assert resolve(reverse("portal:resend_confirmation")).url_name == "resend_confirmation"
    assert resolve(reverse("portal:confirm", args=["resend"])).url_name == "confirm"
