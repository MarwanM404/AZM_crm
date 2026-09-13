"""
No English and no placeholder codes on an Arabic screen (T029, FR-007, FR-009).

A placeholder rendered literally is the defect that started this: the live chat console's
reference heading read `رد: %(REFERENCE)S`, which does not look like a missing translation —
it looks like a broken product. The catalog rules added in this feature stop a wrong
translation being *added*. This is the check that looks at what a reader actually sees, which
is the only place a rendered placeholder can be caught.

It also covers the half no server-side test can reach: strings that appear after the page has
loaded, which is where "Online" and "Offline" survived in English.
"""

import re

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.django_db]

#: Any substitution form this project uses, as it would appear if it reached a reader.
PLACEHOLDER = re.compile(r"%\([a-zA-Z_]+\)[sd]|%\d*[sd]\b|\{[a-zA-Z_]+\}", re.I)

#: Screens an agent can open. The administration screens are swept separately, as an
#: administrator — an agent gets 403 there, and a page reading "403 Forbidden" contains no
#: English body text and no placeholders, so it passes this sweep without rendering anything.
#: Two screens were being reported clean on exactly that basis until a different assertion
#: happened to notice.
SCREENS = [
    "/tickets/",
    "/customers/",
    "/customers/unlinked/",
    "/chat/console/",
    "/chat/supervise/",
]

ADMIN_SCREENS = ["/admin/users/", "/admin/users/new/", "/admin/audit/"]


def visible_text(page):
    """What a reader sees, not the markup. A placeholder inside an attribute is invisible and
    not the defect; one in the body text is."""
    return page.inner_text("body")


@pytest.mark.parametrize("path", SCREENS)
def test_no_placeholder_reaches_the_reader(signed_in_page, live_server, chat_fixtures, path):
    signed_in_page.goto(f"{live_server.url}{path}")
    signed_in_page.wait_for_load_state("networkidle")

    found = PLACEHOLDER.findall(visible_text(signed_in_page))

    assert not found, f"{path} shows placeholder codes to the reader: {found}"


@pytest.mark.parametrize("path", ADMIN_SCREENS)
def test_no_placeholder_reaches_an_administrator_either(admin_page, live_server, path):
    admin_page.goto(f"{live_server.url}{path}")
    admin_page.wait_for_load_state("networkidle")

    assert (
        "403" not in admin_page.inner_text("body")[:40]
    ), f"{path} was not actually rendered; the sweep would pass on the refusal page"
    found = PLACEHOLDER.findall(visible_text(admin_page))

    assert not found, f"{path} shows placeholder codes to the reader: {found}"


def test_the_chat_console_reference_heading_is_arabic(signed_in_page, live_server, chat_fixtures):
    """The specific heading that was reported, kept as its own test so a regression names
    itself rather than appearing as one of seven parametrised paths."""
    signed_in_page.goto(f"{live_server.url}/chat/console/")
    signed_in_page.wait_for_load_state("networkidle")

    text = visible_text(signed_in_page)

    assert "الرقم المرجعي" in text
    assert "%(REFERENCE)S" not in text.upper()


def test_the_status_that_changes_after_load_is_arabic(signed_in_page, live_server, chat_fixtures):
    """The half a server-side test cannot see. "Offline" is rendered by the browser, from a
    catalog that until now was never served — so it stayed English on an Arabic screen."""
    signed_in_page.goto(f"{live_server.url}/chat/console/")
    signed_in_page.wait_for_load_state("networkidle")

    status = signed_in_page.inner_text(".chat-presence")

    assert (
        "Offline" not in status and "Online" not in status
    ), f"the console status is still English: {status!r}"
    assert "متصل" in status


def test_departments_are_named_in_arabic(admin_page, live_server):
    """Stored since the MVP and read nowhere until this feature (FR-008)."""
    admin_page.goto(f"{live_server.url}/admin/users/new/")
    admin_page.wait_for_load_state("networkidle")

    text = visible_text(admin_page)

    assert "403" not in text[:40], "the page was not rendered; the assertion would be vacuous"
    assert "الدعم" in text
