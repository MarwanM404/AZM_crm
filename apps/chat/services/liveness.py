"""
Is each party still on the other end of this conversation? (FR-032 to FR-034)

The same shape as presence, for the same reason research.md #3 gives: a key per party per
conversation, refreshed while they are connected, with a TTL equal to the reconnection grace
period. No key, not present. A `connected = True` column would go on saying "connected"
forever after the process that would have cleared it died.

The distinction worth drawing, because research.md #3 rejected a sweep: it rejected sweeping
as a way to *determine* presence. Determining presence is still the TTL's job — the key is
either there or it is not. The sweep in apps/chat/tasks.py exists only to *act* on an absence
that nothing will otherwise report, because a party who has gone silent sends no event saying
so. Absence is the one state that cannot announce itself.

Seeded when the conversation starts and when an agent is assigned, so a party who never opens
a socket at all is treated as gone after the grace period rather than never considered.
"""

from django.conf import settings

from apps.chat.services.redis_client import get_client

VISITOR = "visitor"
AGENT = "agent"


def _key(conversation_id, party: str) -> str:
    return f"chat:live:{int(conversation_id)}:{party}"


def grace_seconds() -> int:
    return getattr(settings, "CHAT_RECONNECT_GRACE_SECONDS", 60)


def seen(conversation_id, party: str) -> None:
    """Record that this party is on the line, and start the grace period over."""
    client = get_client()
    key = _key(conversation_id, party)
    client.hset(key, mapping={"seen": 1})
    client.expire(key, grace_seconds())


def present(conversation_id, party: str) -> bool:
    return bool(get_client().exists(_key(conversation_id, party)))


def gone(conversation_id, party: str) -> bool:
    """Absent for longer than the grace period — the key has expired."""
    return not present(conversation_id, party)


def forget(conversation_id) -> None:
    """Both parties, when the conversation ends. Nothing should be swept afterwards."""
    client = get_client()
    client.delete(_key(conversation_id, VISITOR), _key(conversation_id, AGENT))
