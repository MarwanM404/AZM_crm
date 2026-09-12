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

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # fast tests only
