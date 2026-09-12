"""
Fixtures for the consumer tests.

Every test here opens at least one socket, and the ones that matter open two — asserting what
the *other* socket did or did not receive is the only honest way to test FR-021 and FR-025.
"""

import pytest
from channels.db import database_sync_to_async

from apps.chat.services import presence, tokens
from apps.chat.services.redis_client import reset_for_tests


@pytest.fixture(autouse=True)
def clean_chat_state():
    reset_for_tests()
    yield
    reset_for_tests()


@pytest.fixture
def conversation(db, department, branch, category, contact):
    """A conversation already assigned, so message tests start from the interesting state."""
    from apps.chat.models import Conversation
    from apps.tickets.models import Ticket

    ticket = Ticket.objects.create(
        contact=contact,
        subject="Chat conversation",
        description="",
        category=category,
        origin_channel=Ticket.Channel.CHAT,
        department=department,
        branch=branch,
    )
    token = tokens.issue(0)  # replaced below once the row has an id
    conversation = Conversation.objects.create(
        ticket=ticket,
        contact=contact,
        visitor_token_hash=tokens.fingerprint(token),
        department=department,
        branch=branch,
    )
    real_token = tokens.issue(conversation.pk)
    conversation.visitor_token_hash = tokens.fingerprint(real_token)
    conversation.save(update_fields=["visitor_token_hash"])
    conversation.test_token = real_token
    return conversation


@pytest.fixture
def assigned_conversation(conversation, agent):
    from django.utils import timezone

    from apps.chat.models import Conversation

    presence.go_online(agent.pk, capacity=3)
    presence.claim_slot(agent.pk)
    conversation.assigned_to = agent
    conversation.state = Conversation.State.ACTIVE
    conversation.assigned_at = timezone.now()
    conversation.save(update_fields=["assigned_to", "state", "assigned_at"])
    return conversation


@database_sync_to_async
def message_count(conversation):
    return conversation.ticket.messages.count()


@database_sync_to_async
def latest_message(conversation):
    return conversation.ticket.messages.order_by("-created_at").first()
