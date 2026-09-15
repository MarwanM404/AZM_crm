"""
Registering, and confirming an address (T032, T033).

Everything interesting here is about the one rule in FR-007: the caller learns nothing. There
are four ways a registration can go — a new address, an address that already has a confirmed
account, one with an unconfirmed account, and one belonging to a member of staff — and all
four return the same thing, take roughly the same time, and differ only in which message is
sent to the address itself.

That last part is what makes the rule workable rather than merely silent. The person who owns
the address always finds out what happened; the person who typed it never does.
"""

from django.contrib.auth.hashers import make_password
from django.db import transaction

from apps.accounts.models import User
from apps.portal import tasks
from apps.portal.models import CustomerAccount, CustomerToken, normalize
from apps.portal.services import tokens


def register(email, password, language):
    """Create an account, or quietly do the appropriate other thing. Returns nothing.

    Returning nothing is deliberate. A caller that cannot see the outcome cannot render a
    different page for it, and the identical-response rule stops being something the view has
    to remember.
    """
    email = normalize(email)

    account = CustomerAccount.objects.filter(email=email).first()

    if account is None and User.objects.filter(email__iexact=email).exists():
        # FR-032: the address belongs to a member of staff. Nothing is created and nothing is
        # sent — sending "somebody tried to register your address" to an agent would turn the
        # form into a way of confirming which addresses are staff, one message at a time.
        _spend_the_same_effort(password)
        return

    if account is None:
        _create(email, password, language)
        return

    _spend_the_same_effort(password)

    if account.is_confirmed:
        # FR-008. The owner is told; the person at the form is told the same thing everyone
        # is told.
        tasks.send_already_registered.delay(email=account.email, language=account.language)
        return

    # Registered before and never confirmed — overwhelmingly "the first message went to
    # spam". Another confirmation, which is also what an attacker retrying gets, so the two
    # remain indistinguishable.
    _issue_confirmation(account)


def _create(email, password, language):
    with transaction.atomic():
        account = CustomerAccount.objects.create_account(
            email=email, password=password, language=language
        )
    _issue_confirmation(account)


def _issue_confirmation(account):
    value, _token = tokens.issue(account, CustomerToken.Purpose.CONFIRMATION)
    tasks.send_confirmation.delay(email=account.email, token_value=value, language=account.language)


def _spend_the_same_effort(password):
    """Hash a password whose result is thrown away.

    Creating an account costs a deliberately slow password hash; the other three paths cost
    nothing. Left alone, that difference is measurable from outside and turns an identical
    response into a distinguishable one — FR-007 satisfied in the body and defeated by the
    clock. The discarded hash buys the branches back their symmetry.
    """
    make_password(password or "")


def confirm(value):
    """Prove an address. Returns the account, or None if the link is no good.

    The account is returned rather than a boolean because the caller signs them in: whoever
    followed the link demonstrably reads that mailbox, which is a stronger proof of identity
    than the password they would otherwise be asked for next.
    """
    token = tokens.consume(value, CustomerToken.Purpose.CONFIRMATION)
    if token is None:
        return None

    account = token.account
    if not account.is_active:
        return None

    if not account.is_confirmed:
        account.confirm()

    return account


def resend_confirmation(email):
    """Ask for another message. Returns nothing, for the same reason `register` does."""
    account = CustomerAccount.objects.filter(email=normalize(email)).first()

    if account is None or account.is_confirmed or not account.is_active:
        return

    _issue_confirmation(account)
