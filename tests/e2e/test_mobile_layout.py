"""
T139, FR-036: every screen is usable on a phone as well as a desktop.

The failures worth catching are structural: a page that scrolls sideways, a table that
overflows its container, or a control too small to hit accurately with a thumb. All three
are invisible at desktop width.
"""

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.django_db]

PHONE = {"width": 390, "height": 844}  # a common current handset
PAGES = ["/tickets/", "/customers/", "/customers/unlinked/"]
MINIMUM_TARGET = 40  # px; below this a thumb misses more often than it hits


@pytest.mark.parametrize("path", PAGES)
def test_no_horizontal_scrolling_on_a_phone(signed_in_page, live_server, path):
    signed_in_page.set_viewport_size(PHONE)
    signed_in_page.goto(f"{live_server.url}{path}")

    overflow = signed_in_page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert overflow <= 1, f"{path} scrolls sideways by {overflow}px at {PHONE['width']}px wide"


def test_ticket_detail_stacks_rather_than_overflowing(signed_in_page, live_server, rtl_fixtures):
    signed_in_page.set_viewport_size(PHONE)
    signed_in_page.goto(f"{live_server.url}/tickets/{rtl_fixtures['ticket'].reference}/")

    overflow = signed_in_page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert overflow <= 1

    # The context sidebar should be below the thread on a phone, not beside it.
    positions = signed_in_page.evaluate(
        """() => {
            const thread = document.querySelector('.detail__thread');
            const side = document.querySelector('.detail__side');
            if (!thread || !side) return null;
            return {threadBottom: thread.getBoundingClientRect().bottom,
                    sideTop: side.getBoundingClientRect().top};
        }"""
    )
    assert positions is not None
    assert (
        positions["sideTop"] >= positions["threadBottom"] - 1
    ), "the context panel is still beside the thread on a phone rather than below it"


def test_public_request_form_fits_a_phone(page, live_server):
    page.set_viewport_size(PHONE)
    page.goto(f"{live_server.url}/request/")

    overflow = page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert overflow <= 1

    submit = page.locator("button[type='submit']").first.bounding_box()
    assert (
        submit["height"] >= MINIMUM_TARGET
    ), f"the submit button is {submit['height']}px tall; a thumb needs about {MINIMUM_TARGET}px"


def test_primary_buttons_are_thumb_sized(signed_in_page, live_server, rtl_fixtures):
    signed_in_page.set_viewport_size(PHONE)
    signed_in_page.goto(f"{live_server.url}/tickets/{rtl_fixtures['ticket'].reference}/")

    too_small = signed_in_page.eval_on_selector_all(
        ".actions .btn, .composer .btn",
        f"""els => els.filter(el => {{
            const r = el.getBoundingClientRect();
            return r.height > 0 && r.height < {MINIMUM_TARGET};
        }}).map(el => {{
            const h = Math.round(el.getBoundingClientRect().height);
            return `${{el.innerText.trim()}}: ${{h}}px`;
        }})""",
    )
    assert not too_small, f"controls below {MINIMUM_TARGET}px tall on a phone: {too_small}"


# --- live chat (T127) ---
#
# Chat is the likeliest of all these screens to be opened on a phone: a customer with a
# problem reaches for whatever is in their hand.

PHONE = {"width": 390, "height": 844}


def test_the_widget_fits_a_phone(page, live_server, chat_fixtures):
    page.set_viewport_size(PHONE)
    page.goto(f"{live_server.url}/chat/widget/")
    page.wait_for_load_state("networkidle")

    overflow = page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert overflow <= 1, f"the widget scrolls sideways by {overflow}px on a 390px screen"


def test_the_widgets_controls_are_reachable_by_thumb(page, live_server, chat_fixtures):
    """A send button smaller than a finger is a send button that gets missed, and on a phone
    the miss lands on whatever is next to it."""
    page.set_viewport_size(PHONE)
    page.goto(f"{live_server.url}/chat/widget/")
    page.wait_for_load_state("networkidle")

    sizes = page.eval_on_selector_all(
        "form.chat-prechat button, form.chat-prechat input:not([type=hidden]), "
        "form.chat-prechat select",
        "els => els.map(el => el.getBoundingClientRect().height)",
    )
    assert sizes, "the pre-chat form rendered no controls"
    too_small = [round(h) for h in sizes if h < 32]
    assert not too_small, f"controls shorter than 32px on a phone: {too_small}"


def test_the_console_fits_a_phone(signed_in_page, live_server, chat_fixtures):
    """Agents work on desktops, but a supervisor checking the desk from a phone is ordinary."""
    signed_in_page.set_viewport_size(PHONE)
    signed_in_page.goto(f"{live_server.url}/chat/console/")
    signed_in_page.wait_for_load_state("networkidle")

    overflow = signed_in_page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert overflow <= 1, f"the console scrolls sideways by {overflow}px on a 390px screen"


def test_the_conversation_fits_a_phone(signed_in_page, live_server, chat_fixtures):
    signed_in_page.set_viewport_size(PHONE)
    signed_in_page.goto(f"{live_server.url}/chat/conversations/{chat_fixtures['conversation'].pk}/")
    signed_in_page.wait_for_load_state("networkidle")

    overflow = signed_in_page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert overflow <= 1, f"the conversation scrolls sideways by {overflow}px"


def test_the_audit_log_fits_a_phone(admin_page, live_server):
    """T063. Its rows used to render sixteen lines of "nothing -> value" each and push the
    table off the screen — on a phone there is nowhere for that to go."""
    admin_page.set_viewport_size(PHONE)
    admin_page.goto(f"{live_server.url}/admin/audit/")
    admin_page.wait_for_load_state("networkidle")

    assert "403" not in admin_page.inner_text("body")[:40], "the page was not rendered"
    overflow = admin_page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )

    assert overflow <= 1, f"the audit log scrolls sideways by {overflow}px on a 390px screen"


def test_an_audit_row_does_not_grow_without_limit(admin_page, live_server):
    """FR-025. Bounded, and scrolling inside its own cell rather than truncated — this is
    evidence, so the remainder has to stay reachable."""
    admin_page.goto(f"{live_server.url}/admin/audit/")
    admin_page.wait_for_load_state("networkidle")

    tallest = admin_page.evaluate(
        """() => Math.max(0, ...[...document.querySelectorAll('.table__row')]
             .map(el => el.getBoundingClientRect().height))"""
    )

    assert tallest <= 220, f"the tallest audit row is {tallest}px"


# --- the customer portal (spec 004, T090) ---
#
# The portal's reader is the likeliest person in this product to be on a phone: a customer
# checking whether anything has happened, from wherever they are, not an agent at a desk. It is
# also the only part of the product whose reader cannot ask an administrator to make it work.

PORTAL_PUBLIC = ["/portal/sign-in/", "/portal/register/", "/portal/reset/"]
PORTAL_PRIVATE = ["/portal/", "/portal/requests/new/"]


@pytest.mark.parametrize("path", PORTAL_PUBLIC)
def test_no_horizontal_scrolling_on_the_public_portal_screens(page, live_server, path):
    page.set_viewport_size(PHONE)
    page.goto(f"{live_server.url}{path}")

    overflow = page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert overflow <= 1, f"{path} scrolls sideways by {overflow}px at {PHONE['width']}px wide"


@pytest.mark.parametrize("path", PORTAL_PRIVATE)
def test_no_horizontal_scrolling_for_a_signed_in_customer(portal_page, live_server, path):
    portal_page.set_viewport_size(PHONE)
    portal_page.goto(f"{live_server.url}{path}")
    portal_page.wait_for_load_state("networkidle")

    assert (
        "/sign-in/" not in portal_page.url
    ), f"{path} redirected to sign-in; this measured the wrong page."
    overflow = portal_page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert overflow <= 1, f"{path} scrolls sideways by {overflow}px at {PHONE['width']}px wide"


def test_the_request_detail_fits_a_phone(portal_page, live_server, portal_fixtures):
    """The screen a customer actually opens on a phone: a long conversation, on a narrow
    viewport, in Arabic."""
    reference = portal_fixtures["ticket"].reference
    portal_page.set_viewport_size(PHONE)
    portal_page.goto(f"{live_server.url}/portal/requests/{reference}/")
    portal_page.wait_for_load_state("networkidle")

    assert "/sign-in/" not in portal_page.url
    overflow = portal_page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert overflow <= 1, f"the request detail scrolls sideways by {overflow}px"


def test_the_reply_box_is_reachable_with_a_thumb(portal_page, live_server, portal_fixtures):
    """A composer narrower than the screen, or a send button below the minimum target, means
    a customer cannot answer from the device they are holding."""
    reference = portal_fixtures["ticket"].reference
    portal_page.set_viewport_size(PHONE)
    portal_page.goto(f"{live_server.url}/portal/requests/{reference}/")
    portal_page.wait_for_load_state("networkidle")

    button = portal_page.eval_on_selector(
        ".reply button[type=submit]",
        "el => { const r = el.getBoundingClientRect(); return {h: r.height, w: r.width}; }",
    )

    assert (
        button["h"] >= MINIMUM_TARGET
    ), f"the send button is {button['h']}px tall; below {MINIMUM_TARGET}px a thumb misses"
