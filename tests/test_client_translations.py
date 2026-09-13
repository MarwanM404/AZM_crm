"""
Strings that arrive from the browser are translated too (T027, T028, FR-007, FR-011).

`gettextOrFallback` in static/js/chat-console.js was already written correctly — it looks for a
real `gettext` and falls back to the source string when there is none. There has never been
one, because the catalog was never routed. So the fallback was not a fallback, it was the only
path, and an Arabic agent read "Online" and "Offline" on an otherwise Arabic screen.

The test that matters here is not that a catalog is served. It is that the Arabic one differs
from the English one: serving a catalog is easy to get right and serving the *wrong* one looks
identical from the server.
"""

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def catalog_for(client, user, language):
    user.language = language
    user.save(update_fields=["language"])
    client.force_login(user)
    return client.get(reverse("javascript-catalog"))


def test_the_catalog_is_served(client, agent):
    response = catalog_for(client, agent, "en")

    assert response.status_code == 200


def test_it_defines_gettext_for_the_page(client, agent):
    """The one thing the client needs. Without this symbol every call takes the fallback."""
    body = catalog_for(client, agent, "en").content.decode()

    assert "gettext" in body


def test_the_arabic_catalog_differs_from_the_english_one(client, agent):
    """Serving a catalog and serving the right catalog look identical from the server. An
    Arabic agent given the English catalog has exactly the defect this is fixing, in a place
    that now appears to be handled."""
    english = catalog_for(client, agent, "en").content.decode()
    arabic = catalog_for(client, agent, "ar").content.decode()

    assert english != arabic


def test_the_arabic_catalog_carries_arabic(client, agent):
    """Read through the escaping, not around it.

    The catalog is JavaScript and escapes non-ASCII as \\uXXXX, so a raw-Arabic substring
    check cannot match however correct the catalog is — the first version of this test failed
    against a perfectly good 14KB catalog and briefly looked like a bug in the feature.
    """
    arabic = catalog_for(client, agent, "ar").content.decode()
    unescaped = arabic.encode("utf-8").decode("unicode_escape")

    assert (
        "غير متصل" in unescaped
    ), "the Arabic catalog contains no Arabic; it is probably the English one"


def test_a_client_string_is_present_to_be_translated(client, agent):
    """The catalog is only useful if it contains the strings the client actually asks for.
    "Offline" is the one that was visible on screen."""
    arabic = catalog_for(client, agent, "ar").content.decode()

    assert "Offline" in arabic


def test_the_client_falls_back_rather_than_rendering_nothing():
    """FR-011. A catalog that failed to load leaves an English label — a degraded product. An
    undefined function leaves a broken one, and the difference matters on a status pill
    somebody reads to decide whether they are taking conversations.

    This guarantee used to live in a `gettextOrFallback` wrapper inside chat-console.js. The
    wrapper was correct and invisible to the extractor — `xgettext` recognises `gettext(...)`
    and not a local wrapper around it — so the strings were never extracted, the catalog never
    held them, and every call took the fallback. Keeping the real name is what makes the
    strings findable; this file is what keeps the fallback.
    """
    from pathlib import Path

    source = (
        Path(__file__).resolve().parent.parent / "static" / "js" / "i18n-fallback.js"
    ).read_text()

    assert "window.gettext = window.gettext ||" in source
    assert "window.interpolate = window.interpolate ||" in source


def test_no_wrapper_hides_the_strings_from_the_extractor():
    """The defect above, as a rule rather than a memory: a wrapper around gettext takes the
    strings out of the extractor's sight, and the symptom is silent."""
    from pathlib import Path

    for path in (Path(__file__).resolve().parent.parent / "static" / "js").glob("chat-*.js"):
        source = path.read_text()
        assert "gettextOrFallback" not in source, (
            f"{path.name} calls a wrapper around gettext; xgettext will not extract its "
            "strings and they will silently render in English"
        )


def test_the_catalog_loads_before_the_scripts_that_use_it():
    """Ordering, which this project has already been caught by once.

    Scripts marked `defer` run in document order, and chat-console.js calls the helper as soon
    as Alpine initialises it. The catalog has to be earlier in the document, or `window.gettext`
    does not exist yet and every string silently takes the fallback — the exact symptom being
    fixed, with the fix apparently in place.
    """
    from pathlib import Path

    base = (Path(__file__).resolve().parent.parent / "templates" / "base.html").read_text()

    catalog_at = base.find("javascript-catalog")
    page_scripts_at = base.find("{% block extra_head %}")

    assert catalog_at != -1, "the catalog is not loaded by the base template"
    assert catalog_at < page_scripts_at, (
        "the translation catalog loads after the page scripts that call gettext; deferred "
        "scripts run in document order, so every client string would take the fallback"
    )


def test_the_catalog_is_reachable_without_signing_in(client):
    """The screens that need it most are the public ones (FR-007).

    The request form and the chat widget are read by anonymous customers. Behind the sign-in
    wall the catalog would 302 for exactly those readers, so the two screens the public
    actually sees would load no translations at all — while every staff screen looked fine.
    """
    response = client.get(reverse("javascript-catalog"))

    assert response.status_code == 200


def test_it_discloses_nothing_but_translations(client):
    """Why making it public is safe: the response is the catalog and nothing else."""
    body = client.get(reverse("javascript-catalog")).content.decode()

    assert "csrftoken" not in body
    assert "sessionid" not in body
