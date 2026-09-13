"""
FR-021: deny by default. Every path except the explicit exemptions redirects an
unauthenticated visitor to sign-in.

This sweeps the whole URL conf rather than listing a few examples, so a new view added
without thought is covered the moment it exists — which is the point of a default-deny rule.
"""

import pytest
from django.conf import settings
from django.urls import URLPattern, URLResolver, get_resolver, reverse

SAMPLE_ARGS = {"reference": "AZM-2026-000001", "pk": "1"}


def _named_routes():
    """Every named route in the project's own apps, with placeholder arguments."""
    routes = []

    def walk(resolver, namespace=None):
        for entry in resolver.url_patterns:
            if isinstance(entry, URLResolver):
                walk(entry, entry.namespace or namespace)
            elif isinstance(entry, URLPattern) and entry.name:
                if namespace in {"admin", "django-admin", None}:
                    continue  # Django's own admin has its own auth; not ours to test here
                name = f"{namespace}:{entry.name}"
                kwargs = {
                    key: SAMPLE_ARGS[key]
                    for key in entry.pattern.regex.groupindex
                    if key in SAMPLE_ARGS
                }
                if len(kwargs) != len(entry.pattern.regex.groupindex):
                    continue  # a route needing arguments we cannot invent
                routes.append((name, kwargs))

    walk(get_resolver())
    return routes


@pytest.mark.django_db
@pytest.mark.parametrize("name,kwargs", _named_routes())
def test_anonymous_visitor_is_denied_or_explicitly_public(client, name, kwargs):
    url = reverse(name, kwargs=kwargs)
    response = client.get(url)

    if name in settings.LOGIN_EXEMPT_URL_NAMES:
        assert response.status_code in (
            200,
            302,
            404,
            405,
        ), f"{name} is exempt but did not respond: {response.status_code}"
        if response.status_code == 302:
            assert (
                reverse("accounts:sign_in") not in response.url
            ), f"{name} is listed as public but redirects to sign-in"
    else:
        assert response.status_code == 302, (
            f"{name} returned {response.status_code} to an anonymous visitor; "
            "every non-exempt path must redirect to sign-in (FR-021)"
        )
        assert reverse("accounts:sign_in") in response.url


def test_exempt_list_is_small_and_deliberate():
    """A growing exemption list is how deny-by-default quietly becomes allow-by-default.

    Pinning the exact set means adding one requires editing this test, which forces the
    question "should this really be public?" to be answered rather than skipped. Each entry
    below carries why it is here:

    - intake:form / intake:submitted — the public request form. Its entire audience is people
      who have no account and never will.
    - accounts:sign_in — you cannot require a session to reach the page that creates one.
    - messaging:inbound_webhook — the sender is a mail provider, not a person. It is
      authenticated by a shared secret compared in constant time, refuses everything if that
      secret is unset, and is covered by apps/messaging/tests/test_inbound_transport.py.
    - chat:availability / chat:widget / chat:start / chat:leave_queue — a chat visitor is
      anonymous by design (live chat FR-005); there is no customer login until the portal
      phase. None of these reads or writes anything belonging to an existing customer: they
      report whether anyone is online, render a form, and create a new conversation. The
      socket that follows is authorized by a signed token naming exactly one conversation.
    - javascript-catalog — translations and nothing else. It has to be public because the two
      screens that need it most are: the request form and the chat widget are read by
      anonymous customers, and behind the wall they would load no catalog at all, leaving an
      Arabic visitor reading English on the only screens the public ever sees. The response
      contains message strings and no data, no identifiers and no tokens, which
      tests/test_client_translations.py asserts rather than assumes.
    - accounts:anonymous_language — the same argument as accounts:sign_in. You cannot require
      a session to reach the control that makes the page readable enough to start one. It
      writes a language cookie and nothing else, validates the code against LANGUAGES, and
      refuses a redirect target outside this host.
    """
    assert settings.LOGIN_EXEMPT_URL_NAMES == {
        "intake:form",
        "intake:submitted",
        "accounts:sign_in",
        "messaging:inbound_webhook",
        "chat:availability",
        "chat:widget",
        "chat:start",
        "chat:leave_queue",
        "javascript-catalog",
        "accounts:anonymous_language",
    }
