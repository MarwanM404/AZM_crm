"""Production settings. Every value is required from the environment; none default to
something usable, so a missing variable fails loudly at startup rather than at a security
incident (constitution: Security & Access Control)."""

from .base import *  # noqa: F401,F403
from .base import env

DEBUG = False
SECRET_KEY = env("DJANGO_SECRET_KEY", required=True)
ALLOWED_HOSTS = [h.strip() for h in env("DJANGO_ALLOWED_HOSTS", required=True).split(",")]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DATABASE_NAME", required=True),
        "USER": env("DATABASE_USER", required=True),
        "PASSWORD": env("DATABASE_PASSWORD", required=True),
        "HOST": env("DATABASE_HOST", required=True),
        "PORT": env("DATABASE_PORT", default="5432"),
        "CONN_MAX_AGE": 60,
    }
}

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": env("REDIS_URL", required=True),
    }
}

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

# Encryption of personal data at rest (constitution: Security & Access Control) is a
# deployment-target property, not application code. See docs/decisions/006-deployment-target.md
# (T144). Nothing here substitutes for it.
