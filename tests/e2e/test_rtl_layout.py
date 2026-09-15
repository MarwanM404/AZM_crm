"""
Right-to-left layout, verified in a real browser (T116, SC-007).

Unit tests can assert that `dir="rtl"` is present. They cannot see that the sidebar is still
painted on the left, that a panel overflows the viewport, or that the internal note's warning
edge is on the wrong side — all of which are the defects Arabic users actually report. These
tests measure the rendered geometry.

Marked `e2e`: run the rest of the suite with `-m "not e2e"` where Playwright's browsers are
not installed.
"""

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.django_db]

SCREENS = ["/tickets/", "/customers/", "/customers/unlinked/"]


def _box(page, selector):
    return page.eval_on_selector(
        selector,
        """el => {
            const r = el.getBoundingClientRect();
            const s = getComputedStyle(el);
            return {
                left: r.left, right: r.right, width: r.width,
                borderInlineStartWidth: s.borderInlineStartWidth,
                borderLeftWidth: s.borderLeftWidth,
                borderRightWidth: s.borderRightWidth,
                textAlign: s.textAlign,
                direction: s.direction,
            };
        }""",
    )


def test_document_direction_is_rtl_for_an_arabic_agent(signed_in_page, live_server):
    signed_in_page.goto(f"{live_server.url}/tickets/")
    assert signed_in_page.evaluate("document.documentElement.dir") == "rtl"
    assert signed_in_page.evaluate("document.documentElement.lang") == "ar"


def test_sidebar_is_painted_on_the_right(signed_in_page, live_server):
    """The layout must actually mirror, not merely declare that it should."""
    signed_in_page.goto(f"{live_server.url}/tickets/")
    nav = _box(signed_in_page, ".shell__nav")
    viewport = signed_in_page.evaluate("document.documentElement.clientWidth")

    assert nav["right"] > viewport / 2, (
        f"The navigation is still on the left in RTL (right edge at {nav['right']} of "
        f"{viewport}). Check for a physical `left`/`border-right` rule."
    )
    assert abs(nav["right"] - viewport) < 2


@pytest.mark.parametrize("path", SCREENS)
def test_no_horizontal_overflow(signed_in_page, live_server, path):
    """A page that scrolls sideways is the classic RTL regression: a physical `left` offset
    or a fixed width pushes content past the viewport edge."""
    signed_in_page.goto(f"{live_server.url}{path}")
    overflow = signed_in_page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert overflow <= 1, f"{path} overflows horizontally by {overflow}px in RTL"


def test_internal_note_edge_is_on_the_inline_start(signed_in_page, live_server, rtl_fixtures):
    """FR-015's visual marker has to be on the reading-start side in both directions. With
    `border-inline-start` that is automatic; with `border-left` it silently lands on the
    wrong side in Arabic and the note stops reading as set apart."""
    signed_in_page.goto(f"{live_server.url}/tickets/{rtl_fixtures['ticket'].reference}/")
    note = _box(signed_in_page, ".msg--internal")

    assert note["direction"] == "rtl"
    assert note["borderRightWidth"] == "4px", (
        "In RTL the internal note's marker must sit on the right (inline-start). It is on "
        f"the left instead: left={note['borderLeftWidth']} right={note['borderRightWidth']}"
    )
    assert note["borderLeftWidth"] in ("0px", "1px")


def test_internal_note_marker_is_more_than_colour(signed_in_page, live_server, rtl_fixtures):
    """T133: the restriction is spelled out in words, so it survives greyscale printing and
    colour blindness."""
    signed_in_page.goto(f"{live_server.url}/tickets/{rtl_fixtures['ticket'].reference}/")
    banner = signed_in_page.inner_text(".msg--internal .msg__banner")
    assert "غير ظاهرة للعميل" in banner


def test_ticket_reference_stays_left_to_right(signed_in_page, live_server, rtl_fixtures):
    """Bidirectional text reorders segments. Without an explicit ltr embedding, a reference
    like AZM-2026-000123 renders with its parts shuffled inside Arabic text."""
    signed_in_page.goto(f"{live_server.url}/tickets/")
    reference = _box(signed_in_page, ".ref")

    assert reference["direction"] == "ltr"
    assert rtl_fixtures["ticket"].reference in signed_in_page.inner_text(".ref")


def test_public_intake_form_is_rtl_without_signing_in(page, live_server):
    """The public form must mirror for Arabic visitors too — they never sign in, so the
    language comes from their browser."""
    page.set_extra_http_headers({"Accept-Language": "ar"})
    page.goto(f"{live_server.url}/request/")

    assert page.evaluate("document.documentElement.dir") == "rtl"
    overflow = page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert overflow <= 1


def test_english_interface_still_reads_left_to_right(page, live_server, rtl_fixtures):
    """The mirror must be conditional, not permanent."""
    agent = rtl_fixtures["agent"]
    agent.language = "en"
    agent.save(update_fields=["language"])

    page.goto(f"{live_server.url}/sign-in/")
    page.fill("input[name='email']", agent.email)
    page.fill("input[name='password']", "rtl-test-password")
    page.click("button[type='submit']")
    page.wait_for_load_state("networkidle")

    assert page.evaluate("document.documentElement.dir") == "ltr"
    nav = _box(page, ".shell__nav")
    assert nav["left"] < 2, "The navigation should be on the left in the English interface"


# --- live chat (T122) ---


def test_the_chat_console_mirrors(signed_in_page, live_server, chat_fixtures):
    signed_in_page.goto(f"{live_server.url}/chat/console/")
    signed_in_page.wait_for_load_state("networkidle")

    assert signed_in_page.evaluate("document.documentElement.dir") == "rtl"
    box = _box(signed_in_page, ".table__row--chat")
    assert box["direction"] == "rtl"


def test_a_chat_message_starts_from_the_right(signed_in_page, live_server, chat_fixtures):
    """A bubble whose text begins on the left is the defect Arabic users report first."""
    signed_in_page.goto(f"{live_server.url}/chat/conversations/{chat_fixtures['conversation'].pk}/")
    signed_in_page.wait_for_load_state("networkidle")

    box = _box(signed_in_page, ".chat-msg")
    assert box["direction"] == "rtl"
    assert box["borderLeftWidth"] != box["borderRightWidth"] or box["borderLeftWidth"] == "0px"


def test_the_chat_thread_does_not_overflow_its_column(signed_in_page, live_server, chat_fixtures):
    """A panel wider than its container pushes a horizontal scrollbar onto the whole page,
    which in RTL scrolls away from the text rather than towards it."""
    signed_in_page.goto(f"{live_server.url}/chat/conversations/{chat_fixtures['conversation'].pk}/")
    signed_in_page.wait_for_load_state("networkidle")

    overflow = signed_in_page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert overflow <= 1, f"the page scrolls horizontally by {overflow}px"


def test_the_visitor_widget_mirrors_for_an_arabic_browser(browser, live_server, chat_fixtures):
    """The customer's panel is the one screen a non-staff Arabic speaker sees.

    Driven with an Arabic browser locale, because a visitor is anonymous: there is no stored
    preference to read, so the language comes from `Accept-Language` exactly as it does on the
    public request form. An English-by-default page for a visitor whose browser asks for
    English is the existing, deliberate behaviour — not a chat defect.
    """
    context = browser.new_context(locale="ar")
    page = context.new_page()
    try:
        page.goto(f"{live_server.url}/chat/widget/")
        page.wait_for_load_state("networkidle")

        assert page.evaluate("document.documentElement.dir") == "rtl"
        overflow = page.evaluate(
            "document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )
        assert overflow <= 1, f"the widget scrolls horizontally by {overflow}px"
    finally:
        page.close()
        context.close()


# --- screens added by spec 003 (T072) ---


def test_the_scope_notice_mirrors(browser, live_server, arabic_agent):
    """Shown to an account with no department, so it needs its own fixture: every other
    signed-in fixture here has one."""
    from apps.accounts.models import User

    stranded = User.objects.create_user(
        email="stranded.rtl@example.com",
        password="rtl-test-password",
        full_name="حساب بلا قسم",
        role=User.Role.ADMINISTRATOR,
        language="ar",
    )
    page = browser.new_page()
    try:
        page.goto(f"{live_server.url}/sign-in/")
        page.fill("input[name='email']", stranded.email)
        page.fill("input[name='password']", "rtl-test-password")
        page.click(".signin__form button[type='submit']")
        page.wait_for_load_state("networkidle")

        assert page.locator(".notice--scope").is_visible()
        overflow = page.evaluate(
            "document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )
        assert overflow <= 1
    finally:
        page.close()


def test_the_audit_log_mirrors(admin_page, live_server):
    admin_page.goto(f"{live_server.url}/admin/audit/")
    admin_page.wait_for_load_state("networkidle")

    assert "403" not in admin_page.inner_text("body")[:40]
    assert admin_page.evaluate("document.documentElement.dir") == "rtl"
    overflow = admin_page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert overflow <= 1


def test_a_reference_in_the_audit_log_reads_left_to_right(admin_page, live_server):
    """Latin text inside a right-to-left page. Without `ltr` the browser truncates from the
    wrong end and every row reads "...-000002", losing what identifies the record."""
    admin_page.goto(f"{live_server.url}/admin/audit/")
    admin_page.wait_for_load_state("networkidle")

    direction = admin_page.eval_on_selector(
        ".table__row--audit:not(.table__row--head) .ltr",
        "el => getComputedStyle(el).direction",
    )

    assert direction == "ltr"


# --- the customer portal (spec 004, T089) ---
#
# The portal has its own chrome rather than the app shell, so nothing above covers it. It is
# also the only part of this product read by people outside the organization, which makes a
# mirrored layout more consequential here than anywhere else: an agent seeing a misplaced
# panel files a bug, a customer closes the tab.

PORTAL_SIGNED_OUT = ["/portal/sign-in/", "/portal/register/", "/portal/reset/"]
PORTAL_SIGNED_IN = ["/portal/", "/portal/requests/new/"]


@pytest.mark.parametrize("path", PORTAL_SIGNED_OUT)
def test_portal_screens_are_rtl_before_signing_in(page, live_server, path):
    """Signed out, which is where an Arabic customer meets this product first — and the set
    of screens most easily forgotten, because every fixture in this file signs somebody in."""
    page.goto(f"{live_server.url}{path}")
    page.click(".lang button[value='ar']")
    page.wait_for_load_state("networkidle")

    assert page.evaluate("document.documentElement.dir") == "rtl"


def assert_signed_in(page, what):
    """The page being measured is the one intended, not the sign-in screen.

    Without this these tests pass on a redirect: the sign-in page is also Arabic, also RTL,
    and also carries the portal chrome, so every assertion below is satisfied by a session
    that silently did not take. It is the same guard test_arabic_sweep uses against its 403
    page, and it caught a real one here while this was being written.
    """
    assert "/sign-in/" not in page.url, (
        f"{what} redirected to sign-in; the customer session did not take, and every "
        "assertion after this would have passed on the wrong page."
    )


@pytest.mark.parametrize("path", PORTAL_SIGNED_IN)
def test_portal_screens_are_rtl_for_an_arabic_customer(portal_page, live_server, path):
    portal_page.goto(f"{live_server.url}{path}")
    portal_page.wait_for_load_state("networkidle")

    assert_signed_in(portal_page, path)
    assert portal_page.evaluate("document.documentElement.dir") == "rtl"


def test_the_brand_sits_on_the_right_in_arabic(portal_page, live_server):
    """The chrome mirrors, not just the text. A header laid out with `left`/`right` rather
    than logical properties keeps the brand on the left and reads as a broken page."""
    portal_page.goto(f"{live_server.url}/portal/")
    portal_page.wait_for_load_state("networkidle")

    assert_signed_in(portal_page, "the request list")
    brand = _box(portal_page, ".portal__head .brand")
    switch = _box(portal_page, ".portal__head .lang")

    assert brand.get("left") > switch.get("left"), (
        "The brand is to the left of the language switch on an Arabic page; the header has "
        "not mirrored."
    )


def test_the_conversation_edge_is_on_the_reading_side(portal_page, live_server, portal_fixtures):
    """`.msg--outbound` carries a coloured `border-inline-start`. With a physical `border-left`
    it would sit on the wrong side in Arabic — which is exactly the defect this file was
    written for, on the staff side, in the MVP."""
    reference = portal_fixtures["ticket"].reference
    portal_page.goto(f"{live_server.url}/portal/requests/{reference}/")
    portal_page.wait_for_load_state("networkidle")

    assert_signed_in(portal_page, "the request detail")
    message = _box(portal_page, ".thread .msg--outbound")
    left = float(message["borderLeftWidth"].rstrip("px"))
    right = float(message["borderRightWidth"].rstrip("px"))

    # Compared, not checked against zero. Every side carries a 1px outline and the marker is
    # the side that is THICKER — written as "the left border is 0px" first, which could not
    # have passed whatever the code did.
    assert right > left, (
        "In Arabic the desk's reply should carry its heavier edge on the right; it has "
        f"{right}px on the right and {left}px on the left."
    )
