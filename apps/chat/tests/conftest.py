"""
Fixtures for the consumer tests.

Every test here opens at least one socket, and the ones that matter open two — asserting what
the *other* socket did or did not receive is the only honest way to test FR-021 and FR-025.

The `conversation` and `assigned_conversation` fixtures live in the root conftest instead:
tests/test_whisper_isolation.py needs them too, and that invariant belongs outside this app
because it spans the visitor consumer, the group naming and the messaging service together.
"""

import pytest
from channels.db import database_sync_to_async

from apps.chat.services.redis_client import reset_for_tests


@pytest.fixture(autouse=True)
def clean_chat_state():
    reset_for_tests()
    yield
    reset_for_tests()


@database_sync_to_async
def message_count(conversation):
    return conversation.ticket.messages.count()


@database_sync_to_async
def latest_message(conversation):
    return conversation.ticket.messages.order_by("-created_at").first()
