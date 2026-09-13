"""
FR-026: a private note is distinct by more than colour (T093, T098).

Colour alone fails three ways that all occur in practice: a colour-blind agent, a greyscale
or high-contrast display, and a tired agent moving fast. The consequence of misreading one is
that a note meant for the agent gets pasted to the customer.

So the distinction is carried four ways at once — a written statement of the restriction, an
icon, a border edge and a background wash — and the first of those survives every failure of
the others. The ticket thread already does this; the chat view matches it rather than
inventing a second visual language for the same boundary.
"""

import re

import pytest
from django.template.loader import render_to_string
from django.urls import reverse

from apps.chat.services import messaging
from apps.chat.services.redis_client import reset_for_tests

pytestmark = pytest.mark.django_db

NOTE = "Check the policy before you answer"


@pytest.fixture(autouse=True)
def clean():
    reset_for_tests()
    yield
    reset_for_tests()


@pytest.fixture
def rendered_note(conversation, supervisor):
    message = messaging.whisper(conversation, supervisor, NOTE)
    return render_to_string(
        "chat/partials/whisper.html", {"message": message, "conversation": conversation}
    )


def test_the_restriction_is_written_out_in_words(rendered_note):
    """The one marker that survives greyscale, colour blindness and a screen reader."""
    assert "cannot see" in rendered_note


def test_it_carries_a_non_colour_marker_as_well(rendered_note):
    """An icon, hidden from screen readers because the words beside it already say it."""
    assert 'aria-hidden="true"' in rendered_note


def test_it_is_marked_by_class_for_edge_and_wash(rendered_note):
    assert "chat-msg--whisper" in rendered_note


def test_a_public_message_carries_none_of_those_markers(conversation, agent):
    """The distinction has to be a difference. A marker on both is a marker on neither."""
    message = messaging.agent_message(conversation, agent, "Of course, one moment")
    rendered = render_to_string(
        "chat/partials/message.html", {"message": message, "conversation": conversation}
    )

    assert "cannot see" not in rendered
    assert "chat-msg--whisper" not in rendered


def test_the_distinction_survives_greyscale(rendered_note):
    """Strip every colour-bearing declaration and the note must still announce itself."""
    without_colour = re.sub(
        r"(background|color|border-color)\s*:[^;\"']+;?", "", rendered_note, flags=re.I
    )

    assert "cannot see" in without_colour


def test_the_agents_live_view_marks_it_the_same_way(agent_client, conversation, supervisor):
    messaging.whisper(conversation, supervisor, NOTE)

    body = agent_client.get(reverse("chat:conversation", args=[conversation.pk])).content.decode()

    assert NOTE in body
    assert "chat-msg--whisper" in body
