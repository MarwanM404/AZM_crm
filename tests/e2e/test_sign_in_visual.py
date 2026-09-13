"""
The first screen looks like the product (T039, T040, FR-013).

It used to drop a bare form into the page with none of the chrome, card or branding every
screen behind it carries. Unit tests cannot see that: the markup was valid and the form
worked. These measure what a reader actually meets.
"""

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.django_db]

PHONE = {"width": 390, "height": 844}


def test_it_carries_the_products_identity(page, live_server):
    page.goto(f"{live_server.url}/sign-in/")
    page.wait_for_load_state("networkidle")

    assert page.locator(".brand").is_visible()
    assert page.locator(".signin__panel").is_visible()


def test_the_form_sits_in_a_card_rather_than_loose_on_the_page(page, live_server):
    """The specific thing that made it look unfinished beside every other screen."""
    page.goto(f"{live_server.url}/sign-in/")
    page.wait_for_load_state("networkidle")

    panel = page.eval_on_selector(
        ".signin__panel",
        """el => {
            const s = getComputedStyle(el);
            return {
                width: el.getBoundingClientRect().width,
                border: parseFloat(s.borderTopWidth),
                radius: parseFloat(s.borderTopLeftRadius),
                background: s.backgroundColor,
            };
        }""",
    )

    assert panel["width"] <= 420, "the form spans the page instead of sitting in a panel"
    assert panel["border"] > 0 or panel["radius"] > 0


def test_it_does_not_scroll_sideways_on_a_phone(page, live_server):
    page.set_viewport_size(PHONE)
    page.goto(f"{live_server.url}/sign-in/")
    page.wait_for_load_state("networkidle")

    overflow = page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )

    assert overflow <= 1, f"the sign-in screen scrolls sideways by {overflow}px"


def test_the_controls_are_reachable_by_thumb(page, live_server):
    page.set_viewport_size(PHONE)
    page.goto(f"{live_server.url}/sign-in/")
    page.wait_for_load_state("networkidle")

    heights = page.eval_on_selector_all(
        # Hidden inputs have no height by definition; measuring them says nothing about
        # whether a finger can reach anything.
        ".signin__form input:not([type=hidden]), .signin__form button",
        "els => els.map(el => el.getBoundingClientRect().height)",
    )

    assert heights
    assert not [round(h) for h in heights if h < 32]


def test_a_language_can_be_chosen_before_signing_in(page, live_server):
    """FR-012. The one screen where the language cannot come from a stored preference."""
    page.goto(f"{live_server.url}/sign-in/")
    page.wait_for_load_state("networkidle")

    page.click(".signin__lang button[value='ar']")
    page.wait_for_load_state("networkidle")

    assert page.evaluate("document.documentElement.dir") == "rtl"
    assert page.evaluate("document.documentElement.lang") == "ar"


def test_the_screen_mirrors_properly_in_arabic(page, live_server):
    page.goto(f"{live_server.url}/sign-in/")
    page.wait_for_load_state("networkidle")
    page.click(".signin__lang button[value='ar']")
    page.wait_for_load_state("networkidle")

    overflow = page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )

    assert overflow <= 1
    assert page.locator(".signin__panel").is_visible()


def test_a_failed_sign_in_shows_its_error_in_the_products_style(page, live_server, arabic_agent):
    """An error that appears in a different visual language than every other error is one the
    reader has to stop and parse."""
    page.goto(f"{live_server.url}/sign-in/")
    page.fill("input[name='email']", arabic_agent.email)
    page.fill("input[name='password']", "definitely-not-the-password")
    page.click(".signin__form button[type='submit']")
    page.wait_for_load_state("networkidle")

    error = page.locator(".error").first
    assert error.is_visible()
    assert error.inner_text().strip()


def test_the_customer_facing_route_is_offered(page, live_server):
    """Somebody who is not staff has arrived at the wrong door, and the right one exists."""
    page.goto(f"{live_server.url}/sign-in/")
    page.wait_for_load_state("networkidle")

    assert page.locator(".signin__foot a").is_visible()
