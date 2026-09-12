"""
CI settings: the test module, but against PostgreSQL.

The suite runs on SQLite locally for speed and because a developer machine may have no
database configured. Some guarantees cannot be checked there — `select_for_update` needs
row-level locking, which SQLite does not have — so those tests skip locally and run here,
against the engine ADR-002 actually specifies.
"""

from .base import env
from .test import *  # noqa: F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DATABASE_NAME", default="azm_crm"),
        "USER": env("DATABASE_USER", default="azm_crm"),
        "PASSWORD": env("DATABASE_PASSWORD", default=""),
        "HOST": env("DATABASE_HOST", default="localhost"),
        "PORT": env("DATABASE_PORT", default="5432"),
    }
}
