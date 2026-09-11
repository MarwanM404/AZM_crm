"""
T133: internal and public messages must be unambiguously distinct in the rendered thread,
by more than colour alone.

Colour fails three ways that matter here: a greyscale print of a ticket, a colour-blind
agent, and a high-contrast display that flattens the palette. So the internal note carries a
written statement of the restriction as well.
"""

import pytest
from django.urls import reverse

from apps.tickets.models import Message


@pytest.fixture
def ticket_with_both(ticket, agent):
    Message.objects.create(
        ticket=ticket,
        author=agent,
        direction=Message.Direction.OUTBOUND,
        visibility=Message.Visibility.PUBLIC,
        channel=ticket.origin_channel,
        body="Public reply to the customer.",
    )
    Message.objects.create(
        ticket=ticket,
        author=agent,
        direction=Message.Direction.OUTBOUND,
        visibility=Message.Visibility.INTERNAL,
        channel=ticket.origin_channel,
        body="Internal note for the team.",
    )
    return ticket


@pytest.mark.django_db
def test_internal_and_public_messages_have_different_markup(english_agent_client, ticket_with_both):
    body = english_agent_client.get(
        reverse("tickets:detail", args=[ticket_with_both.reference])
    ).content.decode()

    assert "msg--internal" in body
    assert "msg--outbound" in body


@pytest.mark.django_db
def test_internal_note_states_the_restriction_in_words(english_agent_client, ticket_with_both):
    body = english_agent_client.get(
        reverse("tickets:detail", args=[ticket_with_both.reference])
    ).content.decode()
    assert "not visible to the customer" in body


@pytest.mark.django_db
def test_the_restriction_is_stated_in_arabic_too(agent_client, ticket_with_both):
    body = agent_client.get(
        reverse("tickets:detail", args=[ticket_with_both.reference])
    ).content.decode()
    assert "غير ظاهرة للعميل" in body


@pytest.mark.django_db
def test_the_composer_separates_reply_from_note_structurally(
    english_agent_client, ticket_with_both
):
    """Two forms posting to two endpoints, not one form with a checkbox: a checkbox has a
    default state, and the default would be the dangerous one."""
    body = english_agent_client.get(
        reverse("tickets:detail", args=[ticket_with_both.reference])
    ).content.decode()

    assert reverse("tickets:reply", args=[ticket_with_both.reference]) in body
    assert reverse("tickets:note", args=[ticket_with_both.reference]) in body
    assert 'type="checkbox"' not in body.split("composer")[-1]
