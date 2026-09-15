"""
The password policy for portal accounts (T034, FR-005, FR-006).

It delegates to `settings.AUTH_PASSWORD_VALIDATORS` rather than defining rules of its own.
That is the point: a portal with its own idea of a strong password gives this product two
answers to the same question, and the two drift. `test_the_policy_is_the_products_configured
_one` fails if this ever grows a rule.

Note what that configuration actually is today. The validators have been in settings since
the MVP and have never been applied to a password anybody chose for themselves — staff
accounts are created by an administrator. This is the first real use of them, and it found
two things worth knowing, both recorded below.
"""

from django.contrib.auth.password_validation import validate_password


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
    from apps.portal.models import CustomerAccount

    validate_password(password or "", user=CustomerAccount(email=email or ""))
