"""
Whispers held for an agent who was not listening (FR-024, T099).

A supervisor types a note the moment the agent's connection drops — a tunnel, a sleeping
laptop, a browser that decided to reload. The note is already persisted, so it is on the
ticket and in the record. What is missing is the delivery: the agent reconnects seconds later
and sees nothing, and the supervisor has no reason to think anything went wrong.

So an undelivered note is held briefly and replayed when that agent's socket returns.

**Keyed by agent as well as conversation, deliberately.** A note is coaching addressed to one
person about how *they* are handling this conversation — "you promised a refund, walk it
back". Replaying that to whoever picks the conversation up instead would hand a stranger a
correction aimed at someone else, about a commitment they never made. Because the key names
the agent, a different agent draining their own key simply finds nothing; nothing has to
remember to check.

Held in Redis with a TTL for the same reason presence is (see presence.py): this state is
supposed to be ephemeral, and a note replayed twenty minutes later lands in a conversation
that has moved on.
"""

from django.conf import settings

from apps.chat.services.redis_client import get_client


def _key(conversation_id, agent_id) -> str:
    return f"chat:pending:{int(conversation_id)}:{int(agent_id)}"


def _grace() -> int:
    """The reconnection grace period (spec assumption: 60 seconds)."""
    return getattr(settings, "CHAT_RECONNECT_GRACE_SECONDS", 60)


def hold(conversation_id, agent_id, *, message_id, html) -> None:
    """Keep one rendered note for this agent on this conversation."""
    client = get_client()
    key = _key(conversation_id, agent_id)
    client.hset(key, mapping={str(int(message_id)): html})
    # Refreshed on every hold: the grace period runs from the last note, so a supervisor
    # writing several during one dropout does not have the first expire mid-sentence.
    client.expire(key, _grace())


def drain(conversation_id, agent_id) -> list[str]:
    """Return the held notes in the order they were written, and forget them.

    Draining is destructive on purpose. A note replayed on every reconnect would repeat
    itself at each flicker of a bad connection, and an agent who sees the same correction
    four times has no way to tell whether it is one note or four.
    """
    client = get_client()
    key = _key(conversation_id, agent_id)
    held = client.hgetall(key)
    if not held:
        return []
    client.delete(key)
    return [html for _message_id, html in sorted(held.items(), key=lambda item: int(item[0]))]


def waiting(conversation_id, agent_id) -> int:
    return len(get_client().hgetall(_key(conversation_id, agent_id)))


def forget(conversation_id, agent_id) -> None:
    get_client().delete(_key(conversation_id, agent_id))
