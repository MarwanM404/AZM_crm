"""
Unread message counts, per agent and per conversation (FR-013).

In Redis, for the same reason presence is: an unread count is a fact about a session, not
about the conversation. It must survive a console reload — an agent who refreshes should not
lose track of which conversations are waiting on them — and it is worthless the moment they
have gone, so nothing should be sweeping a table to clean it up.

Per conversation rather than a single total: an agent holding three needs to know *which* one
is waiting. A total tells them something is happening and nothing about where.
"""

from apps.chat.services.redis_client import get_client


def _key(user_id) -> str:
    return f"chat:unread:{int(user_id)}"


def mark(user_id, conversation_id) -> None:
    client = get_client()
    current = count(user_id, conversation_id)
    client.hset(_key(user_id), mapping={str(int(conversation_id)): current + 1})


def clear(user_id, conversation_id) -> None:
    client = get_client()
    counts = client.hgetall(_key(user_id))
    counts.pop(str(int(conversation_id)), None)
    client.delete(_key(user_id))
    if counts:
        client.hset(_key(user_id), mapping=counts)


def count(user_id, conversation_id) -> int:
    raw = get_client().hgetall(_key(user_id))
    return int(raw.get(str(int(conversation_id)), 0))


def all_for(user_id) -> dict:
    return {int(k): int(v) for k, v in get_client().hgetall(_key(user_id)).items() if int(v)}


def forget(conversation_id, user_ids) -> None:
    """Drop a conversation's count for everyone. Called when it ends — an ended conversation
    still showing unread is a badge nobody can clear."""
    for user_id in user_ids:
        clear(user_id, conversation_id)
