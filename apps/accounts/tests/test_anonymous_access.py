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
    - accounts:quick_sign_in — reachable only when QUICK_SIGN_IN_ENABLED is on, which
      production forces off without reading the environment. The view refuses on that setting
      before anything else, so the exemption grants nothing the setting has not already
      granted; and it must be exempt, because its whole purpose is use by somebody who has not
      signed in. apps/accounts/tests/test_quick_sign_in.py asserts the route refuses when
      disabled, called directly with no control rendered.

    The customer portal (spec 004) adds six, listed together and justified together because
    they are one screen flow rather than six decisions. What they have in common is that each
    is reached by somebody who has no portal session and cannot get one without it — which is
    what makes them exemptions rather than oversights. None of them reads or writes anything
    belonging to an existing customer, and none reveals whether an address is known: FR-007
    requires the response to be identical either way, and
    apps/portal/tests/test_registration.py compares the two as text with only the CSRF token
    and the echoed address masked.

    - portal:register — the screen that exists to be used by somebody with no account.
      Limited per address and per source (FR-010) from settings rather than literals.
    - portal:register_done — "check your email", reached by redirect and shown identically
      whether an account was created, a notice went to the address's real owner, or nothing
      happened at all.
    - portal:confirm — following the link from that message. Authorized by the token in the
      URL, not by a session: unguessable, single use, expiring, and able to do exactly one
      thing. A GET that changes state, which is correct here because a mail client is the
      only thing that can follow it and mail clients do not POST.
    - portal:resend_confirmation — another message, for the one that expired or went to spam.
      Public for the same reason registration is: the person asking cannot sign in, which is
      precisely their problem. Rate limited because it sends mail to an address on request.
    - portal:sign_in — you cannot require a session to reach the page that creates one, which
      is the same argument as accounts:sign_in and is the same argument twice because there
      are two sign-ins in this product and they share nothing else.
    - portal:sign_out — exempt so that a customer whose session has already expired meets an
      ordinary sign-out rather than the STAFF sign-in page, which is what the deny-by-default
      wall would otherwise hand them: a screen they have never seen, for an application they
      have no account in.

    Three more arrive with the password reset (User Story 5), and they share one argument:
    every person who reaches them cannot sign in, which is the definition of their problem.

    - portal:reset — asks for the address. Answers identically whether or not that address has
      an account (FR-007), and is limited per address and per source because it sends mail on
      request: without that it is a way to send somebody a hundred messages from our server.
    - portal:reset_sent — "check your email", shown identically in every case and saying
      nothing about whether anything was sent.
    - portal:reset_confirm — choosing the new password. Authorized by the token in the URL:
      single use, expiring within the hour, and able to do exactly one thing. Completing it
      ends every other session for that account (FR-012) and burns every other outstanding
      link.
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
        "accounts:quick_sign_in",
        "portal:register",
        "portal:register_done",
        "portal:confirm",
        "portal:resend_confirmation",
        "portal:sign_in",
        "portal:sign_out",
        "portal:reset",
        "portal:reset_sent",
        "portal:reset_confirm",
    }
