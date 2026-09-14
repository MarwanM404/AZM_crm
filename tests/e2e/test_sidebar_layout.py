"""
The sidebar is the height of the screen, not of the page (reported 2026-09-14).

`.shell` is a flex row, so its children stretch to the tallest — which is the main content.
On a long page the sidebar becomes as tall as the whole document, and because its footer is
pushed down with `margin-block-start: auto`, the language switcher and the sign-out link end
up at the bottom of the *document* rather than the bottom of the *screen*. On the audit log
that is several thousand pixels away.

The navigation should stay where the reader is. Measured against the viewport rather than
against a pixel count, because the number that matters is "does it fit on the screen".
"""

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.django_db]


def viewport_height(page):
    return page.evaluate("window.innerHeight")


def test_the_sidebar_is_no_taller_than_the_screen(admin_page, live_server):
    """The audit log is the longest page in the product, which is why it was reported."""
    admin_page.goto(f"{live_server.url}/admin/audit/")
    admin_page.wait_for_load_state("networkidle")

    nav = admin_page.eval_on_selector(".shell__nav", "el => el.getBoundingClientRect().height")

    assert nav <= viewport_height(admin_page) + 1, (
        f"the sidebar is {nav}px tall on a {viewport_height(admin_page)}px screen — it is "
        "stretching to the height of the page rather than the height of the window"
    )


def test_the_page_is_still_as_tall_as_its_content(admin_page, live_server):
    """The sidebar stops stretching; the page does not stop scrolling. Capping the wrong
    element would hide the audit entries instead."""
    admin_page.goto(f"{live_server.url}/admin/audit/")
    admin_page.wait_for_load_state("networkidle")

    document = admin_page.evaluate("document.documentElement.scrollHeight")

    assert document > viewport_height(admin_page), (
        "the page no longer scrolls; the content is being clipped rather than the sidebar "
        "being held"
    )


def test_the_sidebar_footer_is_reachable_without_scrolling(admin_page, live_server):
    """Sign out and the language switch live at the bottom of the sidebar. On a long page
    they were at the bottom of the document."""
    admin_page.goto(f"{live_server.url}/admin/audit/")
    admin_page.wait_for_load_state("networkidle")

    bottom = admin_page.eval_on_selector(".shell__foot", "el => el.getBoundingClientRect().bottom")

    assert 0 < bottom <= viewport_height(admin_page) + 1, (
        f"the sidebar footer sits at {bottom}px, below a {viewport_height(admin_page)}px "
        "screen — the reader has to scroll the whole page to sign out"
    )


def test_the_sidebar_stays_put_when_the_page_scrolls(admin_page, live_server):
    """What "stays where the reader is" means, measured."""
    admin_page.goto(f"{live_server.url}/admin/audit/")
    admin_page.wait_for_load_state("networkidle")

    admin_page.evaluate("window.scrollTo(0, 600)")
    admin_page.wait_for_timeout(200)

    top = admin_page.eval_on_selector(".shell__nav", "el => el.getBoundingClientRect().top")

    assert -1 <= top <= 1, f"the sidebar scrolled away; its top is at {top}px"


def test_a_short_page_is_unaffected(admin_page, live_server):
    """The fix must not leave a gap or a scrollbar on the pages that were already fine."""
    admin_page.goto(f"{live_server.url}/admin/users/")
    admin_page.wait_for_load_state("networkidle")

    nav = admin_page.eval_on_selector(".shell__nav", "el => el.getBoundingClientRect().height")

    assert nav <= viewport_height(admin_page) + 1
    assert admin_page.locator(".shell__foot").is_visible()


# --- the narrow layout, where the first version of this fix was wrong ---


NARROW = {"width": 800, "height": 900}


def test_the_narrow_layout_does_not_become_a_screen_of_navigation(admin_page, live_server):
    """Below 860px the shell stacks and the navigation is a banner across the top.

    Holding it to the viewport there makes that banner a full screen tall, so the page starts
    below the fold — which is what the first version of this fix did, and what a test at the
    default viewport could not see.
    """
    admin_page.set_viewport_size(NARROW)
    admin_page.goto(f"{live_server.url}/admin/audit/")
    admin_page.wait_for_load_state("networkidle")

    nav = admin_page.eval_on_selector(".shell__nav", "el => el.getBoundingClientRect().height")

    assert nav < NARROW["height"] / 2, (
        f"the navigation banner is {nav}px of a {NARROW['height']}px screen; the content "
        "starts below the fold"
    )


def test_the_content_is_visible_without_scrolling_when_narrow(admin_page, live_server):
    admin_page.set_viewport_size(NARROW)
    admin_page.goto(f"{live_server.url}/admin/audit/")
    admin_page.wait_for_load_state("networkidle")

    heading = admin_page.eval_on_selector("h1", "el => el.getBoundingClientRect().top")

    assert (
        0 < heading < NARROW["height"]
    ), f"the page heading is at {heading}px on a {NARROW['height']}px screen"
