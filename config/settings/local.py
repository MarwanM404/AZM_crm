"""Local development settings: Postgres via environment variables, Celery eager only if forced."""

from .base import *  # noqa: F401,F403
from .base import env

DEBUG = True
ALLOWED_HOSTS = ["*"]

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

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
