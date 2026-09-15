"""
Putting a test client into a portal session.

One helper rather than the same six lines in every file, because the session now carries a
fingerprint as well as an id (FR-012) and a hand-built session that omits it is simply not
served — which is correct, and which silently broke sixty tests the moment the fingerprint
was added. One place to change is the difference between that and a one-line fix.

Deliberately not `client.post(sign_in)`: a fixture that goes through a screen fails for two
different reasons once that screen exists, and most of these tests are not about signing in.
"""

from django.conf import settings

from apps.portal.auth import CUSTOMER_SESSION_FINGERPRINT, CUSTOMER_SESSION_KEY


def sign_in(client, account):
    session = client.session
    session[CUSTOMER_SESSION_KEY] = account.pk
    session[CUSTOMER_SESSION_FINGERPRINT] = account.session_fingerprint
    session.save()
    client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key
    return client
