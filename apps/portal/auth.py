"""
The portal's own sign-in (T017, T019).

Separate from `django.contrib.auth` on purpose, and the separation is the security property
rather than a side effect. Django's helpers write `_auth_user_id` and resolve it through
`AUTHENTICATION_BACKENDS` into `request.user` — the same `request.user` the deny-by-default
middleware reads and every staff view trusts. A customer signed in with `login()` would BE a
staff session; the only thing keeping them out of the ticket queue would be their lack of a
department, which is precisely what FR-028 forbids relying on.

So the session key is different, the attribute on the request is different
(`request.customer`, set by apps/portal/middleware.py), and `request.user` stays anonymous
for a customer for the whole of their visit.

What is NOT reimplemented: password hashing and comparison, which come from
`django.contrib.auth.hashers` via the model.
"""

import functools

from django.contrib.auth.hashers import check_password, make_password
from django.http import Http404
from django.utils.crypto import constant_time_compare

from apps.portal.models import CustomerAccount, normalize

#: Deliberately not `_auth_user_id`. Two sessions, two keys, no overlap.
CUSTOMER_SESSION_KEY = "_portal_customer_id"

#: What the session was opened against, so a password change can end it (FR-012).
CUSTOMER_SESSION_FINGERPRINT = "_portal_session_fingerprint"

#: Hashed once at import and compared against when no account exists, so that a request for
#: an unknown address costs the same as one for a known address. Without it, sign-in is an
#: enumeration oracle measured in milliseconds: a wrong password takes the full hashing cost,
#: a wrong address returns immediately, and the difference is trivially observable.
_ABSENT_ACCOUNT_HASH = make_password("a-password-that-belongs-to-nobody")


class Unconfirmed(Exception):
    """The credentials are right; the address has not been proved yet.

    A distinct outcome rather than a failed sign-in because telling somebody their password
    is wrong when it is not sends them to the reset flow, which sends them another email they
    did not need, for a problem the first email already solved.

    Disclosing it is safe: whoever is holding the correct password for an unconfirmed account
    is, with overwhelming likelihood, the person who set it minutes ago.
    """

    def __init__(self, account):
        self.account = account
        super().__init__("This address has not been confirmed yet")


def authenticate_customer(email, password, locked_out=None):
    """Return the account, raise `Unconfirmed`, or return None. Never raises for a bad
    password.

    `locked_out` is a list the caller passes in to learn that THIS failure locked the account,
    so it can send the owner exactly one notice. An out-parameter is uglier than a return
    value and is the price of the rule above it: every failure must look identical from
    outside, so the outcome cannot be expressed as a different return.
    """
    account = CustomerAccount.objects.filter(email=normalize(email)).first()

    if account is None:
        # Spend the same time as a real check. The return value is discarded; the cost is
        # the point.
        check_password(password or "", _ABSENT_ACCOUNT_HASH)
        return None

    # Checked BEFORE the password, and the correct password does not get past it. A lock that
    # the right password opens is not a lock — it stops the attacker who is nearly there and
    # nobody else.
    if account.is_locked:
        check_password(password or "", _ABSENT_ACCOUNT_HASH)
        return None

    if not account.check_password(password or ""):
        if account.record_failed_sign_in() and locked_out is not None:
            locked_out.append(account)
        return None

    account.clear_failed_sign_ins()

    # Order matters. Deactivation is checked before confirmation so that a deactivated
    # account cannot be told it merely needs to confirm — that would be an invitation to keep
    # trying, and an admission that the address exists.
    if not account.is_active:
        return None

    if not account.is_confirmed:
        raise Unconfirmed(account)

    return account


def sign_in_customer(request, account):
    """Start a customer session.

    `cycle_key` rotates the session identifier at the privilege boundary, which is what stops
    session fixation: an identifier handed to somebody before they signed in stops being the
    one they hold afterwards.
    """
    request.session.cycle_key()
    request.session[CUSTOMER_SESSION_KEY] = account.pk
    # Stamped so that a password change ends every OTHER session (FR-012) without hunting
    # through the session table. See CustomerAccount.session_fingerprint.
    request.session[CUSTOMER_SESSION_FINGERPRINT] = account.session_fingerprint


def sign_out_customer(request):
    request.session.flush()


def customer_from_session(session):
    """The account this session belongs to, or None.

    Re-read on every request rather than cached on the session. A customer deactivated while
    signed in must stop being served on their next request (FR-031), and a copy of their
    state stored at sign-in would keep serving them until they chose to leave.
    """
    account_id = session.get(CUSTOMER_SESSION_KEY)
    if not account_id:
        return None

    account = CustomerAccount.objects.filter(pk=account_id).first()
    if account is None or not account.may_use_the_portal:
        return None

    # FR-012. A session opened with the old password carries the old fingerprint and stops
    # being served the moment the password changes — which is the whole point of a reset,
    # since the person it is aimed at is usually already signed in somewhere.
    #
    # constant_time_compare rather than `!=`: this is a secret being compared, and the
    # framework provides the comparison for the same reason it provides the hashing.
    stamped = session.get(CUSTOMER_SESSION_FINGERPRINT, "")
    if not constant_time_compare(stamped, account.session_fingerprint):
        return None

    return account


def customer_required(view):
    """Every portal screen behind sign-in wears this.

    It raises 404 today because there is nowhere yet to send anyone: the portal's sign-in
    page arrives with User Story 1 (T035). That is a deferral, not a design — a person who
    simply has not signed in should be shown the sign-in page, and answering "not found" to
    a real page is the unhelpful success spec 003 FR-020 warns about. T035 replaces this with
    a redirect, and test_no_session_is_refused below pins the behaviour so the change is
    deliberate rather than incidental.

    What it must NOT become is a 403. "Forbidden" on a portal route would confirm the route
    exists and is worth attacking; more importantly the same reasoning governs the record
    checks in User Story 2, and the two should not disagree.
    """

    @functools.wraps(view)
    def wrapped(request, *args, **kwargs):
        if getattr(request, "customer", None) is None:
            raise Http404("No customer session")
        return view(request, *args, **kwargs)

    return wrapped
