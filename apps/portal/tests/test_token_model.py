"""
T013. A link that is single use, expiring, and not recoverable from the database.

The storage rule is the one worth arguing about, because it costs nothing and is routinely
skipped. A table of live confirmation and reset links is a table of live credentials: anyone
who can read it — a backup, a replica, an analytics export, a support engineer with a console
— can take over any account that has an unused reset link outstanding. Storing a fingerprint
instead makes the table worthless to a reader while remaining perfectly usable for checking a
link somebody has presented. The chat visitor token already works this way
(apps/chat/services/tokens.py); this follows it.
"""

import pytest
from django.utils import timezone

from apps.portal.models import CustomerToken
from apps.portal.services import tokens

pytestmark = pytest.mark.django_db


def test_the_value_cannot_be_recovered_from_storage(customer):
    value, token = tokens.issue(customer, CustomerToken.Purpose.RESET)

    stored = CustomerToken.objects.get(pk=token.pk)
    assert value not in str(stored.__dict__), (
        "The link value is recoverable from the stored row. Anyone who can read this table "
        "can take over any account with an outstanding reset link."
    )


def test_a_link_works_once(customer):
    value, _ = tokens.issue(customer, CustomerToken.Purpose.CONFIRMATION)

    assert tokens.consume(value, CustomerToken.Purpose.CONFIRMATION) is not None
    assert tokens.consume(value, CustomerToken.Purpose.CONFIRMATION) is None


def test_an_expired_link_does_not_work(customer, settings):
    settings.PORTAL_RESET_LINK_SECONDS = 60
    value, token = tokens.issue(customer, CustomerToken.Purpose.RESET)

    token.expires_at = timezone.now() - timezone.timedelta(seconds=1)
    token.save(update_fields=["expires_at"])

    assert tokens.consume(value, CustomerToken.Purpose.RESET) is None


def test_a_confirmation_link_cannot_reset_a_password(customer):
    """The purposes are separate for a reason. A confirmation link is sent to an address that
    has just been typed into a public form by somebody who may not own it; if that link also
    set a password, registering with a stranger's address would be enough to take it."""
    value, _ = tokens.issue(customer, CustomerToken.Purpose.CONFIRMATION)

    assert tokens.consume(value, CustomerToken.Purpose.RESET) is None


def test_a_reset_link_cannot_confirm_an_address(customer):
    value, _ = tokens.issue(customer, CustomerToken.Purpose.RESET)

    assert tokens.consume(value, CustomerToken.Purpose.CONFIRMATION) is None


def test_a_wrong_value_is_refused(customer):
    tokens.issue(customer, CustomerToken.Purpose.RESET)

    assert tokens.consume("not-the-value", CustomerToken.Purpose.RESET) is None


def test_two_links_are_not_the_same(customer):
    first, _ = tokens.issue(customer, CustomerToken.Purpose.RESET)
    second, _ = tokens.issue(customer, CustomerToken.Purpose.RESET)

    assert first != second


def test_the_two_lifetimes_differ(customer, settings):
    """A reset link hands over the account; a confirmation link proves an address. Giving
    them the same lifetime means one of the two numbers was chosen for the other's risk."""
    _, confirmation = tokens.issue(customer, CustomerToken.Purpose.CONFIRMATION)
    _, reset = tokens.issue(customer, CustomerToken.Purpose.RESET)

    assert reset.expires_at < confirmation.expires_at
