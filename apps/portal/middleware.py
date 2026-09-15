"""
`request.customer`, and the door the portal is behind (T018).

Two jobs, and they are in one middleware because they are two halves of one rule: on a portal
path the actor is a customer and is never a member of staff.

Ordering in settings.MIDDLEWARE matters and is asserted by
apps/portal/tests/test_middleware_order.py:

  * after SessionMiddleware, because it reads the session;
  * after AuthenticationMiddleware, because it needs `request.user` resolved to know whether
    a staff session is present;
  * BEFORE LoginRequiredMiddleware, because that one is deny-by-default and would redirect a
    customer to the staff sign-in page before this one ever ran.

The last point is the subtle one. A customer is anonymous to `request.user`, so the
deny-by-default wall would send them to the STAFF sign-in page. What lets them through is
`_is_a_customer_on_a_portal_path` in apps/core/middleware.py, which requires BOTH a customer
session AND a portal path — a customer session alone must never satisfy that wall, or it
becomes a key to the ticket queue. The portal's pre-sign-in pages are exempted separately and
by name in settings.LOGIN_EXEMPT_URL_NAMES, so the two applications' public surfaces stay
separate lists.
"""

from django.conf import settings
from django.shortcuts import render
from django.urls import Resolver404, resolve
from django.utils import translation

from apps.portal import auth


def is_portal_path(request):
    """True for a path served by apps.portal.

    Resolved rather than prefix-matched. A `startswith("/portal/")` check would be one
    `path()` edit away from being wrong in the dangerous direction — a staff route that
    happened to live under the prefix would be treated as the portal's and have the staff
    wall lifted off it.
    """
    try:
        match = resolve(request.path_info)
    except Resolver404:
        return False
    return match.namespace == "portal"


class CustomerSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Set on EVERY request, not only portal ones. A staff view that asks
        # `request.customer` should get None rather than AttributeError, because a template
        # or view that raises on a missing attribute is one that will be given a
        # `getattr(request, "customer", None)` by the next person, and that swallows the
        # difference between "no customer" and "this code never ran".
        request.customer = auth.customer_from_session(request.session)

        if not is_portal_path(request):
            return self.get_response(request)

        if request.user.is_authenticated:
            return self.refuse_staff(request)

        return self.serve_in_the_customers_language(request)

    def serve_in_the_customers_language(self, request):
        """Activate the customer's stored language for this request (MVP FR-031/FR-033).

        The same defect spec 003 fixed for staff, arriving again by a different door.
        `apps.core.middleware.UserLanguageMiddleware` reads `request.user.language` — and a
        customer is never `request.user`, so without this their preference is written at
        registration and never read once. An Arabic customer signs up in Arabic and every
        page afterwards is English.

        Found by opening the page, not by a test. Thirty-nine tests passed over it, because
        every one of them asserted on status codes and content that happens to be identical
        in both languages.

        `activate` sets the language for the THREAD rather than the request, so it is
        restored afterwards — otherwise it leaks into whatever that thread handles next,
        which in the test suite is the next test.
        """
        language = getattr(request.customer, "language", None)
        if not language or language not in dict(settings.LANGUAGES):
            return self.get_response(request)

        previous = translation.get_language()
        translation.activate(language)
        request.LANGUAGE_CODE = language
        try:
            return self.get_response(request)
        finally:
            if previous:
                translation.activate(previous)
            else:
                translation.deactivate()

    def refuse_staff(self, request):
        """A staff session has asked for a portal page: 403, with an explanation (FR-030).

        403 rather than 404, and the distinction matches how this product already refuses
        things. 404 is for *records* — a ticket, a contact, an attachment — because there the
        status code is itself information: "forbidden" would confirm the reference exists
        (MVP FR-024). Nothing is being confirmed here. The portal's routes are public
        knowledge, the person asking is already inside the building, and the only fact
        disclosed is one they can see in their own address bar.

        What is being refused is a kind of account, not access to a record — which is exactly
        what `apps.accounts.permissions` already raises PermissionDenied for when an agent
        reaches an administrator screen. Answering 404 instead would tell a colleague that a
        real page does not exist, and they would do the sensible thing and report it as
        broken (spec 003, FR-020: do not succeed unhelpfully).

        The explanation matters more than the status code. Without it the agent learns that
        something went wrong and not what, and the most likely next move is to try again in a
        private window — which works, and teaches them the portal is flaky rather than
        separate.

        Deliberately NOT done: signing the staff session out and continuing as an anonymous
        visitor. That would mean a link a customer sends an agent can end that agent's
        working session, which is a denial of service delivered by email.
        """
        return render(
            request,
            "core/portal_is_for_customers.html",
            {"staff_member": request.user},
            status=403,
        )
