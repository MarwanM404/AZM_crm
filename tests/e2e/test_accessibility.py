"""
T138: accessibility checks that a browser can actually decide.

These are not a substitute for a human pass with a screen reader — they cover the mechanical
failures that are easy to introduce and easy to miss: an input with no accessible name, a
control that keyboard users cannot reach, a focus state that is invisible, and text that does
not survive being enlarged.
"""

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.django_db]

PAGES = ["/tickets/", "/customers/", "/customers/unlinked/"]


@pytest.mark.parametrize("path", PAGES)
def test_every_form_control_has_an_accessible_name(signed_in_page, live_server, path):
    """A select or input with no label, aria-label or title is announced as just "edit text"."""
    signed_in_page.goto(f"{live_server.url}{path}")
    unnamed = signed_in_page.eval_on_selector_all(
        "input:not([type=hidden]), select, textarea",
        """els => els.filter(el => {
            if (el.getAttribute('aria-label')) return false;
            if (el.getAttribute('title')) return false;
            if (el.id && document.querySelector(`label[for="${el.id}"]`)) return false;
            if (el.closest('label')) return false;
            return true;
        }).map(el => el.outerHTML.slice(0, 90))""",
    )
    assert not unnamed, f"{path} has controls with no accessible name: {unnamed}"


def test_every_page_has_exactly_one_h1(signed_in_page, live_server):
    for path in PAGES:
        signed_in_page.goto(f"{live_server.url}{path}")
        count = signed_in_page.locator("h1").count()
        assert count == 1, f"{path} has {count} level-one headings"


def test_interactive_controls_are_keyboard_reachable(signed_in_page, live_server):
    """Anything that acts on a click must be a real button or link — a clickable div is
    invisible to keyboard and screen-reader users."""
    signed_in_page.goto(f"{live_server.url}/tickets/")
    unreachable = signed_in_page.eval_on_selector_all(
        "[hx-post], [hx-get]",
        """els => els.filter(el => {
            const tag = el.tagName.toLowerCase();
            if (['button', 'a', 'form', 'input', 'select'].includes(tag)) return false;
            return el.tabIndex < 0;
        }).map(el => el.outerHTML.slice(0, 90))""",
    )
    assert not unreachable, f"not keyboard reachable: {unreachable}"


def test_focused_controls_have_a_visible_focus_style(signed_in_page, live_server):
    """Removing the default outline without replacing it leaves keyboard users with no way
    to tell where they are."""
    signed_in_page.goto(f"{live_server.url}/tickets/")
    signed_in_page.keyboard.press("Tab")

    focus = signed_in_page.evaluate(
        """() => {
            const el = document.activeElement;
            if (!el || el === document.body) return null;
            const s = getComputedStyle(el);
            return {outlineWidth: s.outlineWidth, outlineStyle: s.outlineStyle,
                    boxShadow: s.boxShadow};
        }"""
    )
    assert focus is not None, "tabbing reached nothing focusable"
    has_outline = focus["outlineStyle"] != "none" and focus["outlineWidth"] != "0px"
    has_shadow = focus["boxShadow"] not in ("none", "")
    assert has_outline or has_shadow, f"the focused control shows no focus state: {focus}"


def test_the_page_survives_200_percent_text_size(signed_in_page, live_server):
    """WCAG 1.4.4: text must scale to 200% without content being lost. A layout pinned to
    fixed pixel heights clips instead."""
    signed_in_page.goto(f"{live_server.url}/tickets/")
    signed_in_page.add_style_tag(content="html { font-size: 200% !important; }")

    overflow = signed_in_page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert overflow <= 1, f"the page overflows sideways by {overflow}px at 200% text size"

    h1_visible = signed_in_page.locator("h1").is_visible()
    assert h1_visible


def test_document_declares_its_language(signed_in_page, live_server):
    """Without a lang attribute a screen reader reads Arabic with English pronunciation."""
    signed_in_page.goto(f"{live_server.url}/tickets/")
    assert signed_in_page.evaluate("document.documentElement.lang") in ("ar", "en")


# --- live chat (T128) ---


def test_the_conversation_is_a_live_region(signed_in_page, live_server, chat_fixtures):
    """The one thing chat needs that no other screen here does.

    Everywhere else in this product, new content arrives because the user asked for it — they
    clicked, and they know to look. In a conversation it arrives because somebody else typed.
    Without a live region a screen-reader user is told nothing: the reply is on the page and
    they have no way to know it appeared.
    """
    signed_in_page.goto(f"{live_server.url}/chat/conversations/{chat_fixtures['conversation'].pk}/")
    signed_in_page.wait_for_load_state("networkidle")

    thread = signed_in_page.eval_on_selector(
        "#chat-thread",
        """el => ({
            live: el.getAttribute('aria-live'),
            role: el.getAttribute('role'),
            relevant: el.getAttribute('aria-relevant'),
            label: el.getAttribute('aria-label'),
        })""",
    )

    assert (
        thread["live"] == "polite"
    ), "the conversation is not a live region; an arriving message is announced to nobody"
    assert thread["role"] == "log"
    assert (
        thread["relevant"] == "additions"
    ), "without aria-relevant=additions the whole conversation is re-read on every message"
    assert thread["label"]


def test_the_visitor_widget_is_a_live_region(browser, live_server, chat_fixtures):
    """The customer's side matters more, not less: they have no console to fall back on."""
    context = browser.new_context(locale="ar")
    page = context.new_page()
    try:
        page.goto(f"{live_server.url}/chat/widget/")
        page.wait_for_load_state("networkidle")

        live = page.eval_on_selector("#chat-thread", "el => el.getAttribute('aria-live')")
        assert live == "polite"
    finally:
        page.close()
        context.close()


def test_the_message_composer_is_labelled(signed_in_page, live_server, chat_fixtures):
    """A textarea a screen reader announces only as "edit text"."""
    signed_in_page.goto(f"{live_server.url}/chat/console/")
    signed_in_page.wait_for_load_state("networkidle")

    unlabelled = signed_in_page.eval_on_selector_all(
        "textarea",
        """els => els.filter(el => {
            if (el.getAttribute('aria-label')) return false;
            if (el.id && document.querySelector(`label[for="${el.id}"]`)) return false;
            return !el.closest('label');
        }).map(el => el.className || el.name || '(unnamed)')""",
    )

    assert not unlabelled, f"textareas with no accessible name: {unlabelled}"


def test_the_private_note_is_announced_as_private(signed_in_page, live_server, chat_fixtures):
    """The restriction has to reach a screen reader as words, not as a colour or an icon.

    The lock glyph is aria-hidden precisely so it is not read as "lock" before the sentence
    that actually says what the note is.
    """
    signed_in_page.goto(f"{live_server.url}/chat/conversations/{chat_fixtures['conversation'].pk}/")
    signed_in_page.wait_for_load_state("networkidle")

    text = signed_in_page.inner_text(".chat-msg--whisper")
    assert "لا يراها العميل" in text

    hidden_glyph = signed_in_page.eval_on_selector(
        ".chat-msg--whisper [aria-hidden='true']", "el => el.textContent.trim()"
    )
    assert hidden_glyph


# --- screens added by spec 003 (T072) ---


def test_the_sign_in_form_is_labelled(page, live_server):
    """The first screen anyone meets, and the one a screen reader meets with no context."""
    page.goto(f"{live_server.url}/sign-in/")
    page.wait_for_load_state("networkidle")

    unlabelled = page.eval_on_selector_all(
        ".signin__form input:not([type=hidden])",
        """els => els.filter(el => {
            if (el.getAttribute('aria-label')) return false;
            if (el.id && document.querySelector(`label[for="${el.id}"]`)) return false;
            return !el.closest('label');
        }).map(el => el.name || '(unnamed)')""",
    )

    assert not unlabelled, f"sign-in fields with no accessible name: {unlabelled}"


def test_the_language_choice_says_which_one_is_current(page, live_server):
    """Two buttons that look different and sound identical are one button to a screen
    reader."""
    page.goto(f"{live_server.url}/sign-in/")
    page.wait_for_load_state("networkidle")

    current = page.eval_on_selector_all(
        ".signin__lang button",
        "els => els.filter(el => el.getAttribute('aria-current')).map(el => el.value)",
    )

    assert len(current) == 1, f"{len(current)} language buttons claim to be current"


def test_the_scope_notice_is_reachable_by_keyboard(browser, live_server, arabic_agent):
    """It is the only route out of a product that shows this reader nothing."""
    from apps.accounts.models import User

    stranded = User.objects.create_user(
        email="stranded.a11y@example.com",
        password="rtl-test-password",
        full_name="No Scope",
        role=User.Role.ADMINISTRATOR,
        language="en",
    )
    page = browser.new_page()
    try:
        page.goto(f"{live_server.url}/sign-in/")
        page.fill("input[name='email']", stranded.email)
        page.fill("input[name='password']", "rtl-test-password")
        page.click(".signin__form button[type='submit']")
        page.wait_for_load_state("networkidle")

        unlabelled = page.eval_on_selector_all(
            ".notice--scope select",
            """els => els.filter(el => {
                if (el.getAttribute('aria-label')) return false;
                if (el.id && document.querySelector(`label[for="${el.id}"]`)) return false;
                return !el.closest('label');
            }).map(el => el.name)""",
        )

        assert page.locator(".notice--scope button").is_enabled()
        assert not unlabelled, f"scope-notice fields with no accessible name: {unlabelled}"
    finally:
        page.close()


# --- the customer portal (spec 004, T089) ---
#
# These matter more here than anywhere else in the product. An agent who cannot use a control
# tells somebody; a customer closes the tab, and nobody ever learns why.

PORTAL_PUBLIC = ["/portal/sign-in/", "/portal/register/", "/portal/reset/"]


@pytest.mark.parametrize("path", PORTAL_PUBLIC)
def test_every_public_portal_control_has_an_accessible_name(page, live_server, path):
    page.goto(f"{live_server.url}{path}")

    unnamed = page.eval_on_selector_all(
        "input:not([type=hidden]), select, textarea",
        """els => els.filter(el => {
            if (el.getAttribute('aria-label')) return false;
            if (el.getAttribute('title')) return false;
            if (el.id && document.querySelector(`label[for="${el.id}"]`)) return false;
            if (el.closest('label')) return false;
            return true;
        }).map(el => el.outerHTML.slice(0, 90))""",
    )

    assert not unnamed, f"{path} has form controls with no accessible name: {unnamed}"


def test_the_new_request_form_controls_have_names(portal_page, live_server):
    portal_page.goto(f"{live_server.url}/portal/requests/new/")
    portal_page.wait_for_load_state("networkidle")

    assert "/sign-in/" not in portal_page.url
    unnamed = portal_page.eval_on_selector_all(
        "input:not([type=hidden]), select, textarea",
        """els => els.filter(el => {
            if (el.getAttribute('aria-label')) return false;
            if (el.id && document.querySelector(`label[for="${el.id}"]`)) return false;
            if (el.closest('label')) return false;
            return true;
        }).map(el => el.outerHTML.slice(0, 90))""",
    )

    assert not unnamed, f"the new-request form has unnamed controls: {unnamed}"


def test_a_validation_error_is_associated_with_its_field(page, live_server):
    """A message sitting next to a box is visible; a screen reader announces the box and not
    the message unless they are connected. Django wires `aria-describedby` when a field has
    errors, so this asserts the template renders the errors Django knows about rather than
    reimplementing them in markup of its own."""
    page.goto(f"{live_server.url}/portal/register/")
    page.fill("input[name=email]", "noura@example.com")
    page.fill("input[name=password]", "password")
    page.click(".portal__form button[type=submit]")
    page.wait_for_load_state("networkidle")

    described = page.eval_on_selector(
        "input[name=password]", "el => el.getAttribute('aria-describedby')"
    )
    assert described, (
        "the refused password field is not connected to its error message, so a screen "
        "reader announces the box and never the reason"
    )
    assert page.query_selector(
        f"#{described}"
    ), f"the field points at #{described}, which is not on the page"
