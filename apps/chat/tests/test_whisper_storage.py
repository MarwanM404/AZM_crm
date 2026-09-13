"""
A whisper is an ordinary Message with `visibility=INTERNAL` (T091, T097).

It reuses the MVP's model rather than introducing a parallel one, and that is the point: a
second store for private notes would be a second thing to filter, a second thing to exclude
from transcripts, and a second thing to forget. FR-025 is enforced once, for every internal
message from any channel.
"""

import pytest

from apps.chat.services import messaging
from apps.chat.services.redis_client import reset_for_tests
from apps.tickets.models import Message, Ticket

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clean():
    reset_for_tests()
    yield
    reset_for_tests()


def test_it_is_stored_as_an_internal_chat_message(conversation, supervisor):
    messaging.whisper(conversation, supervisor, "Check the refund policy first")

    note = conversation.ticket.messages.get()
    assert note.visibility == Message.Visibility.INTERNAL
    assert note.channel == Ticket.Channel.CHAT
    assert note.direction == Message.Direction.OUTBOUND


def test_it_records_who_wrote_it(conversation, supervisor):
    """An unattributed note is an anonymous instruction about how to treat a customer."""
    messaging.whisper(conversation, supervisor, "Offer the replacement, not the refund")

    assert conversation.ticket.messages.get().author_id == supervisor.pk


def test_it_lands_on_the_conversations_ticket(conversation, supervisor):
    messaging.whisper(conversation, supervisor, "Noted")

    assert conversation.ticket.messages.get().ticket_id == conversation.ticket_id


def test_it_is_stored_before_it_is_broadcast(conversation, supervisor):
    """research.md #6. A lost delivery is recoverable — the client refetches. A note that was
    broadcast and never stored is absent from the record of a conversation someone may later
    have to account for."""
    from apps.chat.services import messaging as messaging_module

    seen_in_database = []

    def record(group_name, payload):
        seen_in_database.append(Message.objects.filter(body="Ordering matters").exists())

    original = messaging_module._broadcast
    messaging_module._broadcast = record
    try:
        messaging_module.whisper(conversation, supervisor, "Ordering matters")
    finally:
        messaging_module._broadcast = original

    assert seen_in_database and all(seen_in_database)


def test_an_empty_whisper_is_not_stored(conversation, supervisor):
    """A stray Enter should not leave a blank note in a colleague's record."""
    messaging.whisper(conversation, supervisor, "   ")

    assert conversation.ticket.messages.count() == 0


def test_it_does_not_count_as_customer_activity(conversation, supervisor):
    """A whisper is staff talking to staff. Treating it as conversation activity would make a
    conversation look alive while the customer sits waiting."""
    before = conversation.last_activity_at
    messaging.whisper(conversation, supervisor, "Still waiting on the courier")
    conversation.refresh_from_db()

    assert conversation.last_activity_at == before
