"""
FR-027: two destinations, two controls — never one control with a mode (T094).

The failure this prevents is a specific and very human one. An agent or supervisor with a
single composer and a "public / private" toggle will, eventually, send a private remark to a
customer, because the toggle is a small piece of state that is easy to misread when moving
quickly between conversations. Once sent, it cannot be recalled.

So the two are not one control in two modes. They are different controls, on different pages,
posting to different sockets, handled by different consumers. There is no state that decides
which one a given keystroke becomes.
"""

import re

import pytest
from django.urls import reverse

from apps.chat.services import messaging
from apps.chat.services.redis_client import reset_for_tests

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clean():
    reset_for_tests()
    yield
    reset_for_tests()


def supervise_page(client, conversation):
    return client.get(
        reverse("chat:supervise_conversation", args=[conversation.pk])
    ).content.decode()


def agent_page(client, conversation):
    return client.get(reverse("chat:conversation", args=[conversation.pk])).content.decode()


def test_the_supervisors_composer_can_only_send_a_private_note(
    supervisor_client, assigned_conversation
):
    body = supervise_page(supervisor_client, assigned_conversation)

    assert "sendWhisper" in body
    assert "Send private note" in body


def test_the_supervisors_page_offers_no_customer_facing_composer(
    supervisor_client, assigned_conversation
):
    body = supervise_page(supervisor_client, assigned_conversation)

    assert "sendMessage" not in body
    assert "sendReply" not in body


def test_the_supervisors_composer_names_its_restriction_beside_the_box(
    supervisor_client, assigned_conversation
):
    """The label, not a tooltip or a heading further up the page. Whoever is typing is looking
    at the box."""
    body = supervise_page(supervisor_client, assigned_conversation)

    label = body[body.index("chat-whisper__label") : body.index("chat-whisper__input")]
    assert "will not see" in label


def test_neither_page_has_a_visibility_toggle(
    supervisor_client, agent_client, assigned_conversation
):
    """The shape FR-027 forbids: one composer whose destination depends on a control.

    Looked for as a control named for visibility rather than by exact markup, so a select, a
    checkbox or a radio group would all be caught.
    """
    toggle = re.compile(
        r"""<(select|input)[^>]*\bname=["'](visibility|mode|send_as|audience)["']""", re.I
    )

    for body in (
        supervise_page(supervisor_client, assigned_conversation),
        agent_page(agent_client, assigned_conversation),
    ):
        assert not toggle.search(body)


def test_the_two_composers_post_to_different_sockets(
    supervisor_client, agent_client, assigned_conversation
):
    """Different consumers, so neither can become the other by a value being wrong."""
    supervisor_body = supervise_page(supervisor_client, assigned_conversation)
    agent_body = agent_page(agent_client, assigned_conversation)

    assert "/ws/chat/supervise/" in supervisor_body or "chat-observe.js" in supervisor_body
    assert "/ws/chat/supervise/" not in agent_body


def test_the_whisper_frame_type_is_a_literal_not_a_variable():
    """A destination computed at send time is a mode by another name."""
    from pathlib import Path

    source = (Path(__file__).resolve().parents[3] / "static" / "js" / "chat-observe.js").read_text()

    assert 'type: "whisper"' in source
    assert "type: kind" not in source
    assert "type: mode" not in source


def test_the_supervisor_socket_has_no_path_to_a_public_message():
    """The structural guarantee behind the interface one. Even a supervisor sending a crafted
    frame by hand has nothing to reach the customer with."""
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "consumers" / "supervisor.py").read_text()

    assert "messaging.whisper" in source
    for forbidden in (
        "messaging.agent_message",
        "messaging.visitor_message",
        "public_group",
    ):
        assert forbidden not in source, (
            f"apps/chat/consumers/supervisor.py references {forbidden}. An observer must "
            "have no route to the customer at all (FR-022, FR-027)."
        )


def test_a_whisper_and_a_reply_land_with_different_visibility(conversation, agent, supervisor):
    """The end of the guarantee: whatever the interface did, the stored rows differ."""
    from apps.tickets.models import Message

    messaging.whisper(conversation, supervisor, "Private")
    messaging.agent_message(conversation, agent, "Public")

    stored = {m.body: m.visibility for m in conversation.ticket.messages.all()}
    assert stored["Private"] == Message.Visibility.INTERNAL
    assert stored["Public"] == Message.Visibility.PUBLIC
