"""
T133 in a real browser: the internal note stays distinguishable when colour is removed.

The unit tests confirm the marker text is in the markup. Only a browser can confirm it is
actually visible, that the note is still set apart with the palette flattened, and that the
composer's two modes are genuinely separate controls rather than one styled to look like two.
"""

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.django_db]


def _ticket_page(page, live_server, rtl_fixtures):
    page.goto(f"{live_server.url}/tickets/{rtl_fixtures['ticket'].reference}/")
    return page


def test_internal_note_is_visible_and_labelled(signed_in_page, live_server, rtl_fixtures):
    page = _ticket_page(signed_in_page, live_server, rtl_fixtures)

    note = page.locator(".msg--internal")
    assert note.is_visible()
    assert "غير ظاهرة للعميل" in note.inner_text()


def test_note_remains_distinguishable_in_greyscale(signed_in_page, live_server, rtl_fixtures):
    """Force the page to greyscale and confirm the note is still set apart — by its border
    weight and its label — rather than relying on the amber wash alone."""
    page = _ticket_page(signed_in_page, live_server, rtl_fixtures)
    page.add_style_tag(content="html { filter: grayscale(100%) !important; }")

    measurements = page.eval_on_selector_all(
        ".msg",
        """els => els.map(el => {
            const s = getComputedStyle(el);
            return {
                internal: el.classList.contains('msg--internal'),
                borderInlineStart: s.borderInlineStartWidth,
                text: el.innerText.slice(0, 120),
            };
        })""",
    )

    internal = [m for m in measurements if m["internal"]]
    assert internal, "no internal note rendered"
    for note in internal:
        assert note["borderInlineStart"] == "4px"
        assert "غير ظاهرة للعميل" in note["text"], (
            "With colour removed, the only thing separating an internal note from a public "
            "message is its border and its label. The label is missing."
        )


def test_reply_and_note_are_separate_controls(signed_in_page, live_server, rtl_fixtures):
    """Switching to the note tab must change which endpoint the visible form posts to — not
    merely toggle a flag inside one form."""
    page = _ticket_page(signed_in_page, live_server, rtl_fixtures)
    reference = rtl_fixtures["ticket"].reference

    actions = page.eval_on_selector_all(
        ".composer form", "els => els.map(el => el.getAttribute('hx-post'))"
    )
    assert f"/tickets/{reference}/reply/" in actions
    assert f"/tickets/{reference}/note/" in actions
    assert len(set(actions)) == 2, "the two composer modes share a single endpoint"


def test_composer_has_no_checkbox_deciding_visibility(signed_in_page, live_server, rtl_fixtures):
    page = _ticket_page(signed_in_page, live_server, rtl_fixtures)
    checkboxes = page.locator(".composer input[type='checkbox']").count()
    assert checkboxes == 0, (
        "Visibility is decided by which form you submit, not by a checkbox whose unchecked "
        "default would be the dangerous one."
    )
