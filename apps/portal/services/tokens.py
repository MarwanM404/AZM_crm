"""
Single-use, expiring links (T013, T015).

Deliberately parallel to apps/chat/services/tokens.py, which does the same job for a chat
visitor. The shape is the same because the reasoning is: the value travels to the person, a
fingerprint stays here, and the two are compared rather than the value being looked up.
"""

import hashlib
import secrets

from django.conf import settings
from django.utils import timezone

from apps.portal.models import CustomerToken

#: 32 bytes, URL-safe. Long enough that guessing is not a strategy and short enough to
#: survive a mail client wrapping the line it sits on.
TOKEN_BYTES = 32

LIFETIMES = {
    CustomerToken.Purpose.CONFIRMATION: "PORTAL_CONFIRMATION_LINK_SECONDS",
    CustomerToken.Purpose.RESET: "PORTAL_RESET_LINK_SECONDS",
}


def fingerprint(value):
    """SHA-256, not a password hash.

    A password hash is deliberately slow to make guessing expensive; that is the right trade
    for something a human chose and the wrong one for 32 random bytes, which cannot be
    guessed at any speed. Slow hashing here would only mean every confirmation link costs the
    server real work, which is a denial-of-service waiting to be noticed.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def issue(account, purpose):
    """Return `(value, token)`. The value is the only copy; it is not stored."""
    value = secrets.token_urlsafe(TOKEN_BYTES)
    seconds = getattr(settings, LIFETIMES[purpose])
    token = CustomerToken.objects.create(
        account=account,
        purpose=purpose,
        value_hash=fingerprint(value),
        expires_at=timezone.now() + timezone.timedelta(seconds=seconds),
    )
    return value, token


def consume(value, purpose):
    """Return the token if this value is usable for this purpose, else None. Marks it used.

    `purpose` is part of the lookup rather than checked afterwards. Checked afterwards, a
    confirmation link presented to the reset screen would still be found, and the only thing
    stopping a password change would be an `if` somebody could later move.
    """
    if not value:
        return None

    token = (
        CustomerToken.objects.filter(
            value_hash=fingerprint(value), purpose=purpose, used_at__isnull=True
        )
        .select_related("account")
        .first()
    )
    if token is None or not token.is_usable:
        return None

    token.used_at = timezone.now()
    token.save(update_fields=["used_at", "updated_at"])
    return token


def invalidate_all(account, purpose):
    """Burn every outstanding link of one kind.

    Used when a password changes: a reset link still sitting in a mailbox is a second key to
    a lock that was just changed, and the person who changed it believes they are the only
    one holding one.
    """
    CustomerToken.objects.filter(account=account, purpose=purpose, used_at__isnull=True).update(
        used_at=timezone.now()
    )
