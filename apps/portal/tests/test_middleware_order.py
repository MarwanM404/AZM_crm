"""
The portal's middleware sits in the one position that works.

Asserted rather than commented because the failure is silent in one direction and total in
the other. Placed after LoginRequiredMiddleware, every customer is redirected to the STAFF
sign-in page and the portal is simply broken — loud, and someone fixes it. Placed before
AuthenticationMiddleware, `request.user` is not resolved yet, so the staff refusal in
`refuse_staff` never fires and an agent is served customer screens — silent, and nobody
notices.
"""

from django.conf import settings

PORTAL = "apps.portal.middleware.CustomerSessionMiddleware"
SESSION = "django.contrib.sessions.middleware.SessionMiddleware"
AUTH = "django.contrib.auth.middleware.AuthenticationMiddleware"
WALL = "apps.core.middleware.LoginRequiredMiddleware"


def test_it_is_installed():
    assert PORTAL in settings.MIDDLEWARE


def test_it_runs_after_the_session_and_the_staff_user_are_resolved():
    order = settings.MIDDLEWARE

    assert order.index(SESSION) < order.index(PORTAL), "It reads request.session"
    assert order.index(AUTH) < order.index(PORTAL), (
        "It reads request.user to refuse a staff session. Before AuthenticationMiddleware "
        "that check cannot fire, and an agent would be served customer screens."
    )


def test_it_runs_before_the_deny_by_default_wall():
    order = settings.MIDDLEWARE

    assert order.index(PORTAL) < order.index(WALL), (
        "LoginRequiredMiddleware needs request.customer to have been set, or every signed-in "
        "customer is redirected to the staff sign-in page."
    )
