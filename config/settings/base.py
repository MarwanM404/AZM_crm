"""
Base Django settings shared by every environment.

Every value that differs between a developer's machine, CI, and production comes from an
environment variable. Nothing here defaults to a real secret (constitution: Security &
Access Control - secrets outside the repository).
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def env(name, default=None, required=False):
    value = os.environ.get(name, default)
    if required and value is None:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return value


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


SECRET_KEY = env("DJANGO_SECRET_KEY", default="unsafe-placeholder-for-local-dev-only")
DEBUG = env_bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = [h.strip() for h in env("DJANGO_ALLOWED_HOSTS", default="").split(",") if h.strip()]

AUTH_USER_MODEL = "accounts.User"

INSTALLED_APPS = [
    # First on purpose: daphne replaces Django's WSGI-only runserver with an ASGI one, so
    # `manage.py runserver` serves WebSockets in development too (ADR-007). Production runs
    # uvicorn; this exists so developers do not need a second command.
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_htmx",
    "auditlog",
    "apps.core",
    "apps.accounts",
    "apps.customers",
    "apps.tickets",
    "apps.messaging",
    "apps.intake",
    "apps.attachments",
    "apps.chat",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",  # must come after Session, before Common
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "auditlog.middleware.AuditlogMiddleware",  # sets the audit actor from request.user
    "apps.core.middleware.UserLanguageMiddleware",  # user's stored language beats the header
    "apps.core.middleware.LoginRequiredMiddleware",  # deny-by-default; last, sees resolved user
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# --- real-time (ADR-007) ---
# Redis is now REQUIRED rather than merely important: without it there is no chat at all,
# where previously its loss only delayed background jobs.
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [env("REDIS_URL", default="redis://localhost:6379/0")]},
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Internationalization (FR-031 to FR-035) ---
LANGUAGE_CODE = "en"
LANGUAGES = [
    ("ar", "العربية"),
    ("en", "English"),
]
LOCALE_PATHS = [BASE_DIR / "locale"]
USE_I18N = True
USE_TZ = True
TIME_ZONE = "UTC"

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- uploaded files ---
# MEDIA_ROOT deliberately has NO url route: the only way to read a file is
# apps.attachments.views.download, which applies the scope check. MEDIA_URL exists because
# Django wants one, not because anything is served from it.
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
MAX_ATTACHMENT_BYTES = int(env("MAX_ATTACHMENT_BYTES", default=str(10 * 1024 * 1024)))

# --- live chat ---
# These are the numbers most likely to feel wrong once agents actually use the thing, so they
# are settings rather than constants: changing one is an environment edit, not a deployment.
CHAT_DEFAULT_AGENT_CAPACITY = int(env("CHAT_DEFAULT_AGENT_CAPACITY", default="3"))
CHAT_PRESENCE_TTL_SECONDS = int(env("CHAT_PRESENCE_TTL_SECONDS", default="45"))
CHAT_HEARTBEAT_SECONDS = int(env("CHAT_HEARTBEAT_SECONDS", default="20"))
CHAT_RECONNECT_GRACE_SECONDS = int(env("CHAT_RECONNECT_GRACE_SECONDS", default="60"))
CHAT_IDLE_WARNING_SECONDS = int(env("CHAT_IDLE_WARNING_SECONDS", default=str(8 * 60)))
CHAT_IDLE_TIMEOUT_SECONDS = int(env("CHAT_IDLE_TIMEOUT_SECONDS", default=str(10 * 60)))
# Refuse an oversized upload before it is buffered to disk rather than after.
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_ATTACHMENT_BYTES + (1024 * 1024)
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024

# --- Celery (ADR-005) ---
CELERY_BROKER_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "UTC"

# --- Email (contracts/email.md) ---
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="support@example.com")
SUPPORT_EMAIL_DOMAIN = env("SUPPORT_EMAIL_DOMAIN", default="example.com")
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = int(env("EMAIL_PORT", default="587"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", default=True)

# Inbound mail (FR-013). Empty until IT provides a domain and a route — see
# docs/email-setup.md. An unset mode means inbound collection is off, which is a valid state,
# not an error: the threading logic is tested independently of transport.
INBOUND_EMAIL_MODE = env("INBOUND_EMAIL_MODE", default="")  # "webhook" | "imap" | ""
INBOUND_EMAIL_HOST = env("INBOUND_EMAIL_HOST", default="")
INBOUND_EMAIL_USER = env("INBOUND_EMAIL_USER", default="")
INBOUND_EMAIL_PASSWORD = env("INBOUND_EMAIL_PASSWORD", default="")
INBOUND_EMAIL_WEBHOOK_SECRET = env("INBOUND_EMAIL_WEBHOOK_SECRET", default="")
INBOUND_EMAIL_ENABLED = bool(INBOUND_EMAIL_MODE)

# --- Logging: no secrets or PII in logs (constitution: Security & Access Control) ---
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "redact_sensitive": {"()": "apps.core.logging.SensitiveDataFilter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["redact_sensitive"],
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}

# Paths that do not require authentication. Everything else is denied by default
# (constitution: Security & Access Control - deny by default). See apps/core/middleware.py.
LOGIN_EXEMPT_URL_NAMES = {
    "intake:form",
    "intake:submitted",
    "accounts:sign_in",
    # Authenticated by a shared secret rather than a session — the sender is a mail provider,
    # not a person. See apps/messaging/views.py.
    "messaging:inbound_webhook",
}
LOGIN_URL = "accounts:sign_in"
