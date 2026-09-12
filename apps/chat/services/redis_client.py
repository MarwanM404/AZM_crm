"""
The Redis connection for chat state, and a fake for tests.

Presence and the queue are the only things in this project that live outside PostgreSQL. They
are here because they are *supposed* to be ephemeral — see `presence.py`. That makes them
awkward to test against the real thing, so this module hands out a small in-process fake when
Redis is not configured, implementing only the handful of operations chat uses.

The fake is not a general Redis emulator and should not become one. It exists so the
behaviour built on top of Redis — expiry correcting a crashed agent, ordering in the queue —
can be tested on a laptop with nothing installed.
"""

import time

from django.conf import settings


class FakeRedis:
    """Only what chat uses: hashes with expiry, and a sorted set."""

    def __init__(self):
        self._hashes: dict[str, dict[str, str]] = {}
        self._expiry: dict[str, float] = {}
        self._zsets: dict[str, dict[str, float]] = {}

    # --- expiry ---
    def _alive(self, key):
        expires = self._expiry.get(key)
        if expires is not None and expires <= time.monotonic():
            self._hashes.pop(key, None)
            self._expiry.pop(key, None)
            return False
        return key in self._hashes

    def expire(self, key, seconds):
        if key in self._hashes:
            self._expiry[key] = time.monotonic() + seconds
            return True
        return False

    def force_expire(self, key):
        """Test-only: simulate the TTL elapsing without waiting for it."""
        self._hashes.pop(key, None)
        self._expiry.pop(key, None)

    # --- hashes ---
    def hset(self, key, mapping=None, **kwargs):
        values = dict(mapping or {})
        values.update(kwargs)
        self._hashes.setdefault(key, {}).update({k: str(v) for k, v in values.items()})

    def hgetall(self, key):
        return dict(self._hashes[key]) if self._alive(key) else {}

    def exists(self, key):
        return 1 if self._alive(key) else 0

    def delete(self, *keys):
        for key in keys:
            self._hashes.pop(key, None)
            self._expiry.pop(key, None)
            self._zsets.pop(key, None)

    # --- sorted sets ---
    def zadd(self, key, mapping):
        self._zsets.setdefault(key, {}).update(mapping)

    def zrem(self, key, *members):
        for member in members:
            self._zsets.get(key, {}).pop(member, None)

    def zrange(self, key, start, end):
        ordered = sorted(self._zsets.get(key, {}).items(), key=lambda kv: kv[1])
        members = [m for m, _score in ordered]
        return members[start:] if end == -1 else members[start : end + 1]

    def zrank(self, key, member):
        ordered = [m for m, _ in sorted(self._zsets.get(key, {}).items(), key=lambda kv: kv[1])]
        return ordered.index(member) if member in ordered else None

    def zcard(self, key):
        return len(self._zsets.get(key, {}))

    def flushall(self):
        self._hashes.clear()
        self._expiry.clear()
        self._zsets.clear()


_client = None


def get_client():
    """The real client when Redis is configured, the fake otherwise."""
    global _client
    if _client is not None:
        return _client

    url = getattr(settings, "REDIS_URL", "") or ""
    use_fake = getattr(settings, "CHAT_USE_FAKE_REDIS", False)
    if use_fake or not url:
        _client = FakeRedis()
    else:
        import redis

        _client = redis.Redis.from_url(url, decode_responses=True)
    return _client


def reset_for_tests():
    global _client
    if _client is not None:
        _client.flushall()
