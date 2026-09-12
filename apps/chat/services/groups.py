"""
Channel-layer group names — the security boundary of live chat.

Two groups per conversation:

- **public** — the visitor's socket and the assigned agent's. Everything the customer may see.
- **staff** — the assigned agent's socket and any observer's. Whispers go here, and the
  visitor's socket never joins it.

A whisper is therefore not *filtered* away from the customer; there is no wire from it to
them. Leaking one would require actively joining the visitor to the staff group rather than
forgetting a condition.

This lives in its own module and is imported by every consumer, because a boundary derived in
three places will eventually be derived three different ways — and the version that drifts
will be the one nobody tested.

Deliberately **not** offered: any helper returning "the groups for this conversation". A
visitor consumer reaching for that would be handed the staff group, and the mistake would look
like ordinary code.
"""

PREFIX = "chat"


def public_group(conversation_id) -> str:
    """Everything the customer may see. The visitor's socket joins this and only this."""
    return f"{PREFIX}.{int(conversation_id)}.public"


def staff_group(conversation_id) -> str:
    """Staff only: the assigned agent and any observer. Whispers are published here.

    `int()` is not decoration. A conversation id arrives as a string from a URL and as an
    integer from the ORM; without normalising, the same conversation would name two different
    groups depending on where the caller got the id, and a whisper could be published to a
    group the agent's socket had not joined.
    """
    return f"{PREFIX}.{int(conversation_id)}.staff"
