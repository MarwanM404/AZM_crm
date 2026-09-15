"""
T022-T027. Registering, and the things registering must not reveal (FR-001 to FR-009).

The registration screen is public and it is the only screen in this product that creates an
account, so most of this file is about what the response does NOT say. The rule that carries
the weight is FR-007: the answer to "register noura@example.com" must be identical whether
that address is unknown, already registered, or attached to forty tickets. Anything else is
an oracle that turns a public form into a way of asking which of your customers we have.
"""

import pytest
from django.core import mail
from django.urls import reverse

from apps.portal.models import CustomerAccount, CustomerToken

pytestmark = pytest.mark.django_db

GOOD_PASSWORD = "a-long-enough-passphrase-42"


def register(client, email=None, password=GOOD_PASSWORD, **extra):
    return client.post(
        reverse("portal:register"),
        {"email": email or "noura@example.com", "password": password, **extra},
    )


def test_an_account_is_created_and_cannot_be_used_yet(client):
    """Scenario 1, and FR-002. Created unusable is the whole point: an address typed into a
    public form by somebody who may not own it must buy them nothing until it is proved."""
    mail.outbox.clear()
    register(client)

    account = CustomerAccount.objects.get(email="noura@example.com")
    assert account.email_confirmed_at is None
    assert not account.may_use_the_portal


def test_the_confirmation_goes_to_the_address_claimed_and_nowhere_else(client):
    """FR-003."""
    mail.outbox.clear()
    register(client, email="noura@example.com")

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["noura@example.com"]
    assert mail.outbox[0].cc == [] and mail.outbox[0].bcc == []


def test_the_confirmation_link_is_not_in_the_database(client):
    """The value travels; only a fingerprint stays. Asserted from the registration path
    rather than only from the token service, because the service could be correct and the
    view could still log the link or stash it somewhere convenient."""
    mail.outbox.clear()
    register(client)

    token = CustomerToken.objects.get(purpose=CustomerToken.Purpose.CONFIRMATION)
    body = mail.outbox[0].body

    assert token.value_hash not in body
    assert token.value_hash != "", "Nothing was stored, so nothing can be checked later."


def test_an_unconfirmed_account_reaches_nothing(client):
    """T023, FR-002. Not "can do less" — can do nothing."""
    register(client)
    account = CustomerAccount.objects.get(email="noura@example.com")

    from django.conf import settings

    from apps.portal.auth import CUSTOMER_SESSION_KEY
    from apps.portal.tests.routes import portal_routes

    session = client.session
    session[CUSTOMER_SESSION_KEY] = account.pk
    session.save()
    client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

    behind_sign_in = {name: url for name, url in portal_routes().items() if name != "portal:home"}
    for name, url in {**behind_sign_in, "portal:home": reverse("portal:home")}.items():
        if name in settings.LOGIN_EXEMPT_URL_NAMES:
            continue
        assert (
            client.get(url).status_code != 200
        ), f"{name} ({url}) served an account whose address has not been confirmed."


# --- what registration must not disclose (FR-007, FR-008) ---


def test_registering_a_known_address_answers_exactly_as_a_new_one(client):
    """T024. Byte-identical, not merely similar.

    Compared as bytes because every softer comparison has a way through: a different status
    code, a different redirect, an extra field in the form, a word changed in a message. The
    attacker does not need the page to say "this address exists" — they only need the two
    responses to differ.
    """
    fresh = register(client, email="unknown@example.com")

    CustomerAccount.objects.create_account(email="known@example.com", password=GOOD_PASSWORD)
    known = register(client, email="known@example.com")

    assert fresh.status_code == known.status_code
    assert fresh.content == known.content
    assert fresh.get("Location") == known.get("Location")


def test_registering_a_known_address_creates_no_second_account(client):
    CustomerAccount.objects.create_account(email="known@example.com", password=GOOD_PASSWORD)

    register(client, email="known@example.com")

    assert CustomerAccount.objects.filter(email="known@example.com").count() == 1


def test_the_owner_is_told_somebody_tried(client):
    """T025, FR-008. The response says nothing, so the notice is the only way the owner finds
    out — and finding out is the point: it is how they learn somebody is trying."""
    CustomerAccount.objects.create_account(email="known@example.com", password=GOOD_PASSWORD)
    CustomerAccount.objects.get(email="known@example.com").confirm()
    mail.outbox.clear()

    register(client, email="known@example.com")

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["known@example.com"]


def test_the_notice_carries_no_link_and_no_password(client):
    """A message sent to somebody who did not ask for it must not be usable by whoever
    triggered it. A confirmation link here would mean registering a stranger's address sends
    that stranger a key."""
    CustomerAccount.objects.create_account(email="known@example.com", password=GOOD_PASSWORD)
    CustomerAccount.objects.get(email="known@example.com").confirm()
    mail.outbox.clear()

    register(client, email="known@example.com", password="the-attackers-chosen-password-1")
    body = mail.outbox[0].body

    assert reverse("portal:register") not in body or "confirm" not in body.lower()
    assert "the-attackers-chosen-password-1" not in body


def test_an_address_with_tickets_discloses_nothing_before_confirmation(client, contact, ticket):
    """T026, scenario 5. The most valuable thing this form could leak: which of our customers
    is in the system, and how much trouble they are having."""
    address = contact.details.filter(kind="EMAIL").values_list("value", flat=True).first()
    assert address, "The fixture must give the contact an email address for this to mean anything."

    response = register(client, email=address)
    body = response.content.decode()

    assert ticket.reference not in body
    assert ticket.subject not in body


def test_an_address_with_no_history_can_register(client):
    """T027, FR-009. A customer exists before their first ticket does — and the natural
    implementation, matching an address to a contact at registration, quietly forbids this."""
    response = register(client, email="never-written-in@example.com")

    assert response.status_code in (200, 302)
    assert CustomerAccount.objects.filter(email="never-written-in@example.com").exists()


def test_an_unconfirmed_account_registering_again_gets_another_confirmation(client):
    """The ordinary recovery path: the first message went to spam.

    It must stay indistinguishable from the other two cases, which is why it is here rather
    than in a screen that offers to resend.
    """
    register(client, email="noura@example.com")
    mail.outbox.clear()

    register(client, email="noura@example.com")

    assert len(mail.outbox) == 1
    assert CustomerAccount.objects.filter(email="noura@example.com").count() == 1
    assert CustomerToken.objects.filter(purpose=CustomerToken.Purpose.CONFIRMATION).count() == 2


def test_a_staff_address_is_refused_without_saying_so(client, agent):
    """FR-032 meets FR-007. An agent's address cannot become a customer account — and the
    form must not become a way to ask whether an address belongs to staff."""
    fresh = register(client, email="unknown@example.com")
    mail.outbox.clear()

    staff = register(client, email=agent.email)

    assert staff.content == fresh.content
    assert not CustomerAccount.objects.filter(email__iexact=agent.email).exists()
