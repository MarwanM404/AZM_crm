"""
The password policy, and resetting a forgotten one (T034, T083, T084).

The policy delegates to `settings.AUTH_PASSWORD_VALIDATORS` rather than defining rules of its
own. That is the point: a portal with its own idea of a strong password gives this product two
answers to the same question, and the two drift.

Note what that configuration actually is today. The validators have been in settings since the
MVP and had never been applied to a password anybody chose for themselves — staff accounts are
created by an administrator. This is the first real use of them, and it found two things worth
knowing, both recorded on `validate` below.
"""

from django.contrib.auth.password_validation import validate_password

from apps.portal import tasks
from apps.portal.models import CustomerAccount, CustomerToken, normalize
from apps.portal.services import tokens


def validate(password, email=None):
    """Raise `django.core.exceptions.ValidationError` if the password is not good enough.

    Raises rather than returning a verdict so that a caller which forgets to check the result
    cannot accidentally accept everything — the failure mode of a boolean here is a policy
    that is configured, called, and ignored.

    The `user` argument is an unsaved `CustomerAccount`, and getting it right took two tries:

      * Passing `None` — the obvious choice, since no account exists yet when somebody
        registers — makes `UserAttributeSimilarityValidator` find nothing to compare against
        and approve every password. It does not error and it does not warn; it simply stops
        being a check, which is the worst way for a security control to fail.
      * Passing a small stand-in object with an `email` attribute gets further and then
        crashes: the validator reaches for `user._meta.get_field(...).verbose_name` to write
        its error message, and catches only `FieldDoesNotExist`. A duck-typed object raises
        `AttributeError` and takes the request down — but only on the path where the password
        is BAD, so a suite that tests good passwords never sees it.

    An unsaved model instance has both the attribute and the `_meta`, and is never written.
    """
    validate_password(password or "", user=CustomerAccount(email=email or ""))


# --- resetting a forgotten password (FR-007, FR-012) ---


def start_reset(email):
    """Send a reset link, or quietly do nothing. Returns nothing either way.

    Returning nothing is the mechanism, not a style choice: a caller that cannot see the
    outcome cannot render a different page for it, so FR-007 stops being something the view
    has to remember. It is the same shape as `registration.register`, for the same reason.

    An unconfirmed account gets no reset. Nobody has proved they own that address, so whoever
    registered it — possibly a stranger who typed it in — could wait for the real owner to
    ask for a reset and inherit the account. Confirming is the way in from there.
    """
    account = CustomerAccount.objects.filter(email=normalize(email)).first()

    if account is None or not account.may_use_the_portal:
        return

    value, _token = tokens.issue(account, CustomerToken.Purpose.RESET)
    tasks.send_reset.delay(email=account.email, token_value=value, language=account.language)


def complete_reset(value, new_password):
    """Set a new password from a reset link. Returns the account, or None if the link is no
    good.

    The link is consumed only once the password is known to be acceptable. Burning it on a
    rejected password would cost somebody their link for a typo — somebody who is, by
    definition, already locked out and already frustrated, and whose next step would be to
    start the whole flow again.
    """
    token = tokens.peek(value, CustomerToken.Purpose.RESET)
    if token is None:
        return None

    account = token.account
    if not account.may_use_the_portal:
        return None

    validate(new_password, email=account.email)

    token.consume()
    account.set_password(new_password)
    account.save(update_fields=["password", "updated_at"])

    # Every other outstanding link is a second key to a lock that was just changed, held by
    # somebody who believes they are the only one holding one.
    tokens.invalidate_all(account, CustomerToken.Purpose.RESET)

    # The lock has been answered: whoever did this demonstrably reads the mailbox, which is a
    # stronger proof than the password the lock was protecting. Leaving them locked out after
    # the only remedy the product offers is a dead end.
    account.clear_failed_sign_ins()

    return account
