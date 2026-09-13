"""
An account with no department or branch is told so (T016, T017, FR-004).

This is the other half of the reported defect, and the half that looks worse. The first
administrator on a new installation has no scope, because the command that creates one never
asks. Every scoped screen then filters for records with no department — which matches almost
nothing — so the product appears empty to the one person who can fix it, on their first visit.

Nothing is wrong, in the sense that nothing failed. Scoping is working exactly as written. The
emptiness is real and its cause is invisible, which is why an explanation rather than a filter
change is the fix.
"""

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db

SCOPED_SCREENS = ["administration:users", "tickets:queue", "customers:list"]


@pytest.fixture
def scopeless_administrator(db):
    """Created the way a new installation creates its first account: no scope, because
    nothing asked for one."""
    from apps.accounts.models import User

    # English, so the assertions below read the words they are checking. The Arabic side is
    # checked explicitly at the end of this file rather than left to whichever language
    # happened to be the default — a mistake made once already in this feature.
    return User.objects.create_superuser(
        email="root@example.com", password="bootstrap-pw", full_name="Root", language="en"
    )


@pytest.fixture
def scopeless_client(scopeless_administrator):
    from django.test import Client

    own = Client()
    own.force_login(scopeless_administrator)
    return own


@pytest.mark.parametrize("screen", SCOPED_SCREENS)
def test_the_emptiness_is_explained_rather_than_shown(
    scopeless_client, screen, department, branch, ticket
):
    body = scopeless_client.get(reverse(screen)).content.decode()

    assert "no department or branch" in body.lower(), (
        f"{screen} appears empty with no indication that the cause is the viewer's own "
        "account having no scope"
    )


def test_the_explanation_says_how_to_fix_it(scopeless_client, department, branch):
    """ "Your account has no scope" without a next step is a dead end on the first screen
    anyone sees."""
    body = scopeless_client.get(reverse("administration:users")).content.decode()

    assert reverse("administration:own_scope") in body


@pytest.mark.parametrize("screen", SCOPED_SCREENS)
def test_a_scoped_administrator_sees_none_of_it(admin_client_, screen, department, branch, ticket):
    """An explanation shown to everybody explains nothing, and would appear on every genuinely
    empty screen in the product."""
    body = admin_client_.get(reverse(screen)).content.decode()

    assert "no department or branch" not in body.lower()


def test_a_genuinely_empty_screen_still_says_it_is_empty(
    admin_client_, administrator, department, branch
):
    """The ordinary empty state must survive. A scoped administrator with no tickets is not
    misconfigured, and telling them they are would be a new defect."""
    administrator.language = "en"
    administrator.save(update_fields=["language"])

    body = admin_client_.get(reverse("tickets:queue")).content.decode()

    assert "no tickets" in body.lower()
    assert "no department or branch" not in body.lower()


def test_an_agent_without_a_scope_is_told_too(client, db, department, branch, ticket):
    """Rarer than the administrator case — an account is normally created with a scope — but
    the screen should not assume the reader can fix it themselves."""
    from apps.accounts.models import User

    stranded = User.objects.create_user(
        email="stranded@example.com",
        password="x",
        full_name="Stranded",
        role=User.Role.AGENT,
        language="en",
    )
    client.force_login(stranded)

    body = client.get(reverse("tickets:queue")).content.decode()

    assert "no department or branch" in body.lower()


def test_the_explanation_exists_in_arabic_too(scopeless_administrator, department, branch):
    """An explanation only half this desk can read is not an explanation. Checked against the
    catalog rather than a hardcoded phrase, so the test survives a reworded translation."""
    from django.test import Client
    from django.utils import translation

    scopeless_administrator.language = "ar"
    scopeless_administrator.save(update_fields=["language"])
    own = Client()
    own.force_login(scopeless_administrator)

    with translation.override("ar"):
        expected = translation.gettext(
            "Your account has no department or branch, so there is nothing for it to show."
        )
    assert (
        expected != "Your account has no department or branch, so there is nothing for it to show."
    ), "the explanation has no Arabic translation"

    body = own.get(reverse("administration:users")).content.decode()
    assert expected in body
