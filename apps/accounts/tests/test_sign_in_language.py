"""
Choosing a language before there is an account to remember it (T037, T038, FR-012, FR-014).

The existing switcher writes `request.user.language`, so it needs an account and cannot serve
the sign-in screen at all. An Arabic speaker therefore arrives at an English page with no way
to change it — on the one screen where the language cannot come from a stored preference,
because the preference is behind the thing they are trying to reach.

FR-014 is the part that is easy to leave out and would make the switch pointless: a language
chosen on the way in has to survive the sign-in that follows. Without it, someone deliberately
picks Arabic, signs in, and lands on an English page one request later.
"""

import pytest
from django.conf import settings
from django.urls import reverse

pytestmark = pytest.mark.django_db


def choose(client, language):
    return client.post(reverse("accounts:anonymous_language"), {"language": language}, follow=True)


def test_an_anonymous_visitor_can_choose_arabic(client):
    response = choose(client, "ar")

    assert response.status_code == 200
    assert client.cookies[settings.LANGUAGE_COOKIE_NAME].value == "ar"


def test_the_choice_takes_effect_immediately(client):
    """The failure this project has already made once: a language switch that answered
    "nothing changed" and appeared to do nothing until the page was reloaded by hand."""
    choose(client, "ar")

    body = client.get(reverse("accounts:sign_in")).content.decode()

    assert 'lang="ar"' in body
    assert 'dir="rtl"' in body


def test_english_can_be_chosen_too(client):
    choose(client, "ar")
    choose(client, "en")

    body = client.get(reverse("accounts:sign_in")).content.decode()

    assert 'lang="en"' in body


def test_an_unsupported_language_is_refused(client):
    response = client.post(reverse("accounts:anonymous_language"), {"language": "fr"})

    assert response.status_code == 400


def test_a_missing_language_is_refused(client):
    response = client.post(reverse("accounts:anonymous_language"), {})

    assert response.status_code == 400


def test_it_only_ever_returns_to_this_site(client):
    """`next` comes from the request, so an unchecked redirect here is an open redirect — the
    same rule the signed-in switcher already follows."""
    response = client.post(
        reverse("accounts:anonymous_language"),
        {"language": "ar", "next": "https://example.com/phish"},
    )

    assert response.status_code in (302, 200)
    assert "example.com" not in response.get("Location", "")


def test_it_needs_no_account(client):
    """The whole point: it is reachable by someone who has not signed in.

    Both outcomes redirect to /sign-in/ and they mean opposite things — the login wall sends
    you there with `?next=`, and this view sends you back there as its fallback target when
    there is no Referer. The `?next=` is what distinguishes "you were turned away" from "you
    were returned to the page you were on".
    """
    response = client.post(reverse("accounts:anonymous_language"), {"language": "ar"})

    assert "next=" not in response.get("Location", ""), (
        "the route is behind the sign-in wall, so the control that makes the sign-in page "
        "readable cannot be reached from the sign-in page"
    )
    assert client.cookies[settings.LANGUAGE_COOKIE_NAME].value == "ar"


# --- FR-014: the choice survives signing in ---


def test_a_language_chosen_before_signing_in_is_adopted(client, agent):
    """Otherwise the switch is decorative: pick Arabic, sign in, land on English."""
    agent.language = "en"
    agent.save(update_fields=["language"])
    choose(client, "ar")

    client.post(
        reverse("accounts:sign_in"),
        {"email": agent.email, "password": "pw"},
    )
    agent.refresh_from_db()

    assert agent.language == "ar"


def test_the_session_that_follows_is_in_that_language(client, agent):
    agent.language = "en"
    agent.save(update_fields=["language"])
    choose(client, "ar")

    client.post(
        reverse("accounts:sign_in"),
        {"email": agent.email, "password": "pw"},
    )
    body = client.get(reverse("tickets:queue")).content.decode()

    assert 'dir="rtl"' in body


def test_signing_in_without_choosing_leaves_the_preference_alone(client, agent):
    """Only a deliberate choice overrides a stored preference. Someone who signs in without
    touching the switch keeps the language they set last time."""
    agent.language = "en"
    agent.save(update_fields=["language"])

    client.post(
        reverse("accounts:sign_in"),
        {"email": agent.email, "password": "pw"},
    )
    agent.refresh_from_db()

    assert agent.language == "en"
