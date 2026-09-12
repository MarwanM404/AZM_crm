"""
The waiting queue (FR-016, FR-017, FR-019, FR-042).

A Redis sorted set scored by arrival time, one per department and branch. A sorted set gives
"longest waiting first" and "what position am I" as single operations, which a list would
turn into a scan.

Scoped like every other collection in this product: a queue that ignored department and branch
would route a visitor to an agent who cannot see their tickets.

Entries are seconds to minutes old, so losing them to a Redis restart is a small loss with a
defined behaviour (FR-042 already requires offering the request form) rather than an unhandled
one.
"""

import time

from apps.chat.services.redis_client import get_client


def _key(department_id, branch_id) -> str:
    return f"chat:queue:{int(department_id)}:{int(branch_id)}"


def join(token: str, department_id, branch_id) -> None:
    """Place a visitor in the queue. Joining twice is not two places: a visitor with two
    browser tabs is one person waiting."""
    client = get_client()
    key = _key(department_id, branch_id)
    if client.zrank(key, token) is None:
        client.zadd(key, {token: time.time()})


def leave(token: str, department_id, branch_id) -> None:
    get_client().zrem(_key(department_id, branch_id), token)


def position(token: str, department_id, branch_id):
    """1-based, or None when not waiting. Shown to the visitor and updated as it changes."""
    rank = get_client().zrank(_key(department_id, branch_id), token)
    return None if rank is None else rank + 1


def waiting_count(department_id, branch_id) -> int:
    return get_client().zcard(_key(department_id, branch_id))


def take_next(department_id, branch_id):
    """The longest-waiting visitor, removed from the queue. None when nobody is waiting."""
    client = get_client()
    key = _key(department_id, branch_id)
    head = client.zrange(key, 0, 0)
    if not head:
        return None
    token = head[0]
    client.zrem(key, token)
    return token


def drain(department_id, branch_id) -> list:
    """Everyone waiting, removed, in order.

    Used when the last online agent goes offline (FR-042): the visitors are moved to the
    request form rather than left queued for a desk that has closed.
    """
    client = get_client()
    key = _key(department_id, branch_id)
    waiting = client.zrange(key, 0, -1)
    if waiting:
        client.zrem(key, *waiting)
    return list(waiting)
