"""
Agent presence and capacity (FR-011, FR-012).

Stored in Redis with a TTL, for the inverse of the usual reason: presence is *supposed* to be
ephemeral. An agent whose browser closed, whose laptop slept, or whose server restarted is not
online — and a database row saying "online" would go on saying so, because the process that
would have corrected it is the one that died.

No heartbeat, no key, not online. The failure mode corrects itself rather than needing a sweep
to compensate for having chosen durable storage for ephemeral state.
"""

from django.conf import settings

from apps.chat.services.redis_client import get_client
from apps.chat.services.redis_client import reset_for_tests as _reset


def _key(user_id) -> str:
    return f"chat:presence:{int(user_id)}"


def _ttl() -> int:
    return getattr(settings, "CHAT_PRESENCE_TTL_SECONDS", 45)


def go_online(user_id, capacity=None) -> None:
    capacity = capacity or getattr(settings, "CHAT_DEFAULT_AGENT_CAPACITY", 3)
    client = get_client()
    client.hset(_key(user_id), mapping={"capacity": capacity, "active": 0})
    client.expire(_key(user_id), _ttl())


def go_offline(user_id) -> None:
    get_client().delete(_key(user_id))


def heartbeat(user_id) -> bool:
    """Refresh the TTL. Returns False for an agent who is not online.

    Deliberately does NOT recreate the key: an agent who went offline on purpose must stay
    offline, or a stale browser tab would silently re-enlist someone who had finished.
    """
    return bool(get_client().expire(_key(user_id), _ttl()))


def is_online(user_id) -> bool:
    return bool(get_client().exists(_key(user_id)))


def _state(user_id):
    raw = get_client().hgetall(_key(user_id))
    if not raw:
        return None
    return int(raw.get("capacity", 0)), int(raw.get("active", 0))


def capacity_remaining(user_id) -> int:
    state = _state(user_id)
    if state is None:
        return 0
    capacity, active = state
    return max(0, capacity - active)


def has_capacity(user_id) -> bool:
    return capacity_remaining(user_id) > 0


def claim_slot(user_id) -> bool:
    """Take one conversation's worth of capacity. False when there is none left."""
    state = _state(user_id)
    if state is None:
        return False
    capacity, active = state
    if active >= capacity:
        return False
    client = get_client()
    client.hset(_key(user_id), mapping={"active": active + 1})
    client.expire(_key(user_id), _ttl())
    return True


def release_slot(user_id) -> None:
    """Give a slot back. Never drops below zero: releasing more than was claimed is a bug
    elsewhere, and must not leave an agent looking infinitely available."""
    state = _state(user_id)
    if state is None:
        return
    _capacity, active = state
    client = get_client()
    client.hset(_key(user_id), mapping={"active": max(0, active - 1)})
    client.expire(_key(user_id), _ttl())


def agents_with_capacity(user_ids) -> list:
    return [uid for uid in user_ids if is_online(uid) and has_capacity(uid)]


def anyone_online(user_ids) -> bool:
    """FR-039 hangs off this: with nobody online, chat is not offered at all."""
    return any(is_online(uid) for uid in user_ids)


def active_count(user_id) -> int:
    state = _state(user_id)
    return state[1] if state else 0


# --- test helpers ---


def reset_for_tests() -> None:
    _reset()


def expire_now_for_tests(user_id) -> None:
    """Simulate the TTL elapsing, without a test having to sleep for it."""
    client = get_client()
    if hasattr(client, "force_expire"):
        client.force_expire(_key(user_id))
    else:
        client.delete(_key(user_id))


# --- socket presence ---
#
# Distinct from `is_online`, which answers "is this agent taking conversations". An agent can
# be online and momentarily unreachable: the tunnel, the sleeping laptop, the reloading tab.
# Whispers care about the second question, because a note broadcast to a group with no live
# member is simply lost.


def _socket_key(user_id) -> str:
    return f"chat:socket:{int(user_id)}"


def socket_opened(user_id) -> None:
    client = get_client()
    client.hset(_socket_key(user_id), mapping={"open": 1})
    # A TTL as a backstop: a process killed between connect and disconnect would otherwise
    # leave this saying "reachable" forever, and whispers would be dropped rather than held.
    client.expire(_socket_key(user_id), _ttl() * 4)


def socket_closed(user_id) -> None:
    get_client().delete(_socket_key(user_id))


def has_socket(user_id) -> bool:
    return bool(get_client().exists(_socket_key(user_id)))
