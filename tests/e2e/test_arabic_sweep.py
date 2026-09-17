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


def test_the_sign_in_screen_is_fully_arabic(browser, live_server):
    """Signed out, so `signed_in_page` cannot reach it — which is why it was missing from the
    sweep above, and why two English strings survived a passing Arabic suite until somebody
    looked at the page.
    """
    context = browser.new_context(locale="ar")
    page = context.new_page()
    try:
        page.goto(f"{live_server.url}/sign-in/")
        page.wait_for_load_state("networkidle")

        text = page.inner_text("body")
        assert not PLACEHOLDER.findall(text)
        assert "Customer support desk" not in text
        assert "Not a member of staff" not in text
        assert "مكتب دعم العملاء" in text
    finally:
        page.close()
        context.close()


def test_departments_are_named_in_arabic(admin_page, live_server):
    """Stored since the MVP and read nowhere until this feature (FR-008)."""
    admin_page.goto(f"{live_server.url}/admin/users/new/")
    admin_page.wait_for_load_state("networkidle")

    text = visible_text(admin_page)

    assert "403" not in text[:40], "the page was not rendered; the assertion would be vacuous"
    assert "الدعم" in text


# --- the customer portal (spec 004, T091) ---
#
# Swept signed out AND signed in, because the signed-out half is the half that was missed
# before: every fixture in this file signs somebody in, so the screens an Arabic visitor
# actually meets first were the ones nobody looked at.

PORTAL_PUBLIC = [
    "/portal/sign-in/",
    "/portal/register/",
    "/portal/register/done/",
    "/portal/reset/",
    "/portal/reset/sent/",
    "/portal/resend/",
]

PORTAL_PRIVATE = ["/portal/", "/portal/requests/new/"]


def in_arabic(page, live_server, path):
    page.goto(f"{live_server.url}{path}")
    page.click(".lang button[value='ar']")
    page.wait_for_load_state("networkidle")
    page.goto(f"{live_server.url}{path}")
    page.wait_for_load_state("networkidle")
    return page


@pytest.mark.parametrize("path", PORTAL_PUBLIC)
def test_no_placeholder_on_a_public_portal_screen(page, live_server, path):
    in_arabic(page, live_server, path)

    found = PLACEHOLDER.findall(visible_text(page))

    assert not found, f"{path} shows placeholder codes to the reader: {found}"


@pytest.mark.parametrize("path", PORTAL_PUBLIC)
def test_no_english_on_a_public_portal_screen(page, live_server, path):
    """The language switch itself says "English", and that is the point of it — everything
    else on the page must be Arabic."""
    in_arabic(page, live_server, path)

    text = visible_text(page).replace("English", "").replace("AZM", "")
    latin_words = re.findall(r"\b[A-Za-z]{4,}\b", text)

    assert not latin_words, f"{path} shows English to an Arabic reader: {latin_words}"


@pytest.mark.parametrize("path", PORTAL_PRIVATE)
def test_no_placeholder_for_a_signed_in_customer(portal_page, live_server, path):
    portal_page.goto(f"{live_server.url}{path}")
    portal_page.wait_for_load_state("networkidle")

    assert (
        "/sign-in/" not in portal_page.url
    ), f"{path} redirected to sign-in; the sweep would have passed on that page instead"
    found = PLACEHOLDER.findall(visible_text(portal_page))

    assert not found, f"{path} shows placeholder codes to the reader: {found}"


def test_the_request_detail_is_arabic(portal_page, live_server, portal_fixtures):
    reference = portal_fixtures["ticket"].reference
    portal_page.goto(f"{live_server.url}/portal/requests/{reference}/")
    portal_page.wait_for_load_state("networkidle")

    assert "/sign-in/" not in portal_page.url
    text = visible_text(portal_page)

    assert not PLACEHOLDER.findall(text)
    assert "طلبك" in text, "the customer's own opening words are not labelled in Arabic"


def test_the_internal_note_is_absent_from_the_rendered_page(
    portal_page, live_server, portal_fixtures
):
    """The boundary, checked in a real browser rather than in a template render.

    Everything server-side already asserts this. What only a browser can say is that nothing
    put it there afterwards — a fragment, a data attribute read by script, a cached response.
    """
    reference = portal_fixtures["ticket"].reference
    portal_page.goto(f"{live_server.url}/portal/requests/{reference}/")
    portal_page.wait_for_load_state("networkidle")

    assert "INTERNAL-NOTE-THE-CUSTOMER-MUST-NEVER-SEE" not in portal_page.content()


# --- the public screens, which were never swept in a browser ---
#
# The request form, the page after submitting, and the chat widget. Every SCREENS entry above
# is behind a staff sign-in, and these three are the only ones an anonymous customer ever sees
# — so the screens read by the people least able to report a problem were the ones nobody
# looked at.
#
# Noticed while adding portal links to two of them: text was going onto a public page that no
# browser check covered.


@pytest.fixture
def public_fixtures(arabic_agent):
    from apps.chat.services import presence
    from apps.customers.services.matching import find_or_create_contact
    from apps.tickets.models import Category, Ticket

    department, branch = arabic_agent.department, arabic_agent.branch
    category = Category.objects.create(
        name="Logistics", name_ar="الخدمات اللوجستية", department=department
    )
    contact, _ = find_or_create_contact(
        full_name="سارة أحمد", email="sara@example.com", department=department, branch=branch
    )
    ticket = Ticket.objects.create(
        contact=contact,
        subject="لم تصل الشحنة",
        description="...",
        category=category,
        origin_channel=Ticket.Channel.WEB_FORM,
        department=department,
        branch=branch,
    )
    # The widget renders its "desk closed" branch otherwise, which is a different screen.
    presence.go_online(arabic_agent.pk, capacity=3)
    return {"ticket": ticket, "category": category}


def as_arabic_visitor(page, live_server, path):
    """Arabic set by cookie, not by clicking a switch.

    These three screens have no language switcher — unlike the portal and the staff sign-in
    page — so `in_arabic` above times out on them. A visitor's language is set by their
    browser's Accept-Language or by the cookie either way, and the cookie is the same mechanism
    accounts:anonymous_language writes.
    """
    from django.conf import settings

    page.context.add_cookies(
        [
            {
                "name": settings.LANGUAGE_COOKIE_NAME,
                "value": "ar",
                "url": live_server.url,
            }
        ]
    )
    page.goto(f"{live_server.url}{path}")
    page.wait_for_load_state("networkidle")
    return page


def public_paths(fixtures):
    return [
        "/request/",
        f"/request/submitted/{fixtures['ticket'].reference}/",
        "/chat/widget/",
    ]


def test_no_placeholder_reaches_an_anonymous_arabic_customer(page, live_server, public_fixtures):
    for path in public_paths(public_fixtures):
        as_arabic_visitor(page, live_server, path)

        found = PLACEHOLDER.findall(visible_text(page))

        assert not found, f"{path} shows placeholder codes to the reader: {found}"


def test_no_english_reaches_an_anonymous_arabic_customer(page, live_server, public_fixtures):
    """The reference itself is Latin by design — AZM-2026-000001 — and so is the brand."""
    for path in public_paths(public_fixtures):
        as_arabic_visitor(page, live_server, path)

        text = visible_text(page).replace("English", "").replace("AZM", "")
        text = re.sub(r"\b[A-Z]{2,}-\d{4}-\d+\b", "", text)
        latin_words = re.findall(r"\b[A-Za-z]{4,}\b", text)

        assert not latin_words, f"{path} shows English to an Arabic reader: {latin_words}"
