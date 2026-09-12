"""
Test settings.

Uses SQLite rather than PostgreSQL: this sandbox has no usable database credentials and no
privilege to create one (see plan.md Technical Context, which names SQLite for local test
runs). Production and local-development runtime settings target PostgreSQL per ADR-002
unchanged; only the automated test suite runs against SQLite here.

Celery tasks run eagerly (synchronously, in-process) so tests do not need a live Redis
broker. This is the standard Django/Celery testing pattern, not a change to ADR-005.
"""

from .base import *  # noqa: F401,F403
from .base import BASE_DIR

DEBUG = False
SECRET_KEY = "test-secret-key-not-for-production-use"
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "test_db.sqlite3",
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# An in-memory channel layer: consumer tests need no Redis. This is safe because the layer
# itself is Channels' code, not ours — what the tests exercise is which groups a consumer
# joins and what each socket therefore receives, and that is identical on either backend.
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

# Presence and the queue use an in-process fake rather than a real Redis, so the behaviour
# built on top of it — expiry correcting a crashed agent, queue ordering — is testable on a
# machine with nothing installed. See apps/chat/services/redis_client.py.
CHAT_USE_FAKE_REDIS = True

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # fast tests only

# Test uploads go to a throwaway directory, never the real media tree.
import tempfile  # noqa: E402
from pathlib import Path as _Path  # noqa: E402

MEDIA_ROOT = _Path(tempfile.mkdtemp(prefix="azm-test-media-"))
