"""
The private note, seen the way an agent sees it (T123, FR-026).

The unit tests confirm the marker text is in the markup. Only a browser can confirm it is
actually visible, and that the note stays distinguishable with the palette flattened — which
is what a colour-blind agent, a greyscale display, and a tired agent moving quickly all
amount to.

The consequence of misreading one is that a note meant for the agent is pasted to a customer,
so "distinguishable" has to mean distinguishable without colour, not merely coloured.
"""

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.django_db]


def _conversation_page(page, live_server, chat_fixtures):
    page.goto(f"{live_server.url}/chat/conversations/{chat_fixtures['conversation'].pk}/")
    page.wait_for_load_state("networkidle")
    return page


def test_the_note_is_visible_and_says_what_it_is(signed_in_page, live_server, chat_fixtures):
    page = _conversation_page(signed_in_page, live_server, chat_fixtures)

    note = page.locator(".chat-msg--whisper")
    assert note.is_visible()
    assert "لا يراها العميل" in note.inner_text()


def test_the_note_is_distinguishable_in_greyscale(signed_in_page, live_server, chat_fixtures):
    page = _conversation_page(signed_in_page, live_server, chat_fixtures)
    page.add_style_tag(content="html { filter: grayscale(100%) !important; }")

    measured = page.eval_on_selector_all(
        ".chat-msg",
        """els => els.map(el => {
            const s = getComputedStyle(el);
            return {
                whisper: el.classList.contains('chat-msg--whisper'),
                borderInlineStart: parseFloat(s.borderInlineStartWidth),
                text: el.innerText,
            };
        })""",
    )

    notes = [m for m in measured if m["whisper"]]
    ordinary = [m for m in measured if not m["whisper"]]
    assert notes and ordinary

    assert notes[0]["borderInlineStart"] > ordinary[0]["borderInlineStart"], (
        "with colour removed the private note has the same edge as a customer message; the "
        "distinction is carried by the wash alone (FR-026)"
    )
    assert "لا يراها العميل" in notes[0]["text"]


def test_the_customer_message_carries_no_such_marking(signed_in_page, live_server, chat_fixtures):
    """A marker on both is a marker on neither."""
    page = _conversation_page(signed_in_page, live_server, chat_fixtures)

    ordinary = page.locator(".chat-msg:not(.chat-msg--whisper)").first
    assert "لا يراها العميل" not in ordinary.inner_text()


def test_the_notes_edge_is_on_the_right_in_arabic(signed_in_page, live_server, chat_fixtures):
    """A warning edge painted on the wrong side of an RTL layout reads as decoration."""
    page = _conversation_page(signed_in_page, live_server, chat_fixtures)

    edges = page.eval_on_selector(
        ".chat-msg--whisper",
        """el => {
            const s = getComputedStyle(el);
            return {left: parseFloat(s.borderLeftWidth), right: parseFloat(s.borderRightWidth)};
        }""",
    )

    assert edges["right"] > edges["left"], (
        "the private note's edge is painted on the left in a right-to-left layout — a "
        "physical `border-left` somewhere instead of `border-inline-start`"
    )
