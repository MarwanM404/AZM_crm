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
