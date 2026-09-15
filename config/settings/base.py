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
    "apps.portal",
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
    # Before the deny-by-default wall, which would otherwise redirect every customer to the
    # STAFF sign-in page before the portal ever saw the request. See apps/portal/middleware.py.
    "apps.portal.middleware.CustomerSessionMiddleware",
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
                # FR-004: the scope notice belongs on every scoped screen, and
                # adding it view by view means every future view must remember.
                "apps.core.context_processors.scope_notice",
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
    # The visitor is anonymous by design (FR-005): there is no customer login until the
    # portal phase. The socket that follows is authorized by a signed token, not a session.
    "chat:availability",
    "chat:widget",
    "chat:start",
    "chat:leave_queue",
    # Translations only, no data of any kind. It must be public because the screens that need
    # it most are: the request form and the chat widget are read by anonymous customers, and
    # behind the sign-in wall they would load no catalog at all — leaving an Arabic visitor
    # reading English on the two screens the public actually sees.
    "javascript-catalog",
    # Choosing a language before signing in. It has to be public for the same reason the
    # sign-in page itself does: you cannot require a session to reach the control that makes
    # the page readable enough to start one.
    "accounts:anonymous_language",
    # Reachable only when QUICK_SIGN_IN_ENABLED is on, which production forces off without
    # reading the environment. The view refuses on the setting before anything else, so
    # exempting it from the sign-in wall grants nothing that the setting has not already
    # granted — and it must be exempt, because its entire purpose is to be used by somebody
    # who has not signed in.
    "accounts:quick_sign_in",
}
LOGIN_URL = "accounts:sign_in"


# FR-042: nobody waits for a desk that has closed. An agent whose laptop slept fires no event
# — their presence key simply expires — so this is swept rather than handled. A minute is
# chosen against the reconnection grace period (60s): long enough that a brief dropout does
# not evict a queue, short enough that nobody waits materially past the desk closing.
# Spec assumptions, to be confirmed with agents before release — the two numbers most likely
# to feel wrong in practice (spec.md, Assumptions).
CHAT_RECONNECT_GRACE_SECONDS = 60
CHAT_IDLE_LIMIT_SECONDS = 600
CHAT_IDLE_WARNING_SECONDS = 480


# --- The customer portal (spec 004) -----------------------------------------------------
#
# Every limit below is expressed twice, per address and per source, because they stop
# different attacks. Per address stops one account being ground down; per source stops one
# machine working through a list of addresses. A limit on only one of them looks like rate
# limiting and is not.
#
# Rates are django-ratelimit strings and are read by apps/portal/views.py.

# Creating an account. The per-address figure matches the anonymous request form's, which has
# survived contact with the public since the MVP.
PORTAL_REGISTER_RATE_PER_ADDRESS = "5/h"
PORTAL_REGISTER_RATE_PER_SOURCE = "20/h"

# Signing in. Looser than registration because a person who has forgotten which password they
# used will legitimately try several times, and a limit that punishes them teaches them to
# give up rather than teaching an attacker anything. The lockout below is the real defence.
PORTAL_SIGN_IN_RATE_PER_ADDRESS = "10/h"
PORTAL_SIGN_IN_RATE_PER_SOURCE = "30/h"

# Asking for a password reset, and asking for another confirmation message. Both send mail to
# an address the requester has not proved they own, so the limit is also what stops this
# product being used to send somebody a hundred emails.
PORTAL_RESET_RATE_PER_ADDRESS = "5/h"
PORTAL_RESET_RATE_PER_SOURCE = "20/h"
PORTAL_CONFIRM_RESEND_RATE_PER_ADDRESS = "5/h"
PORTAL_CONFIRM_RESEND_RATE_PER_SOURCE = "20/h"

# Writing. Generous, because these are the portal working as intended: a customer in a live
# back-and-forth about an urgent problem should not meet a limit, and the limit exists for
# the script, not the person.
PORTAL_REPLY_RATE_PER_ADDRESS = "30/h"
PORTAL_REPLY_RATE_PER_SOURCE = "60/h"
PORTAL_NEW_REQUEST_RATE_PER_ADDRESS = "10/h"
PORTAL_NEW_REQUEST_RATE_PER_SOURCE = "20/h"

# Lockout after repeated failures (FR-011). Deliberately a lockout with an end rather than
# one an administrator must lift: this product has no self-service unlock for staff and no
# support queue a locked-out customer could reach, so a lock that needs a human to release it
# is a customer who cannot get help — and the person most likely to be locked out is the
# legitimate owner having a bad morning.
PORTAL_LOCKOUT_THRESHOLD = 10
PORTAL_LOCKOUT_SECONDS = 900

# How long a link in an email stays usable. The two numbers differ because the two links are
# worth different amounts: a confirmation link proves an address, a reset link hands over the
# account. A message sits in a mailbox indefinitely and may be forwarded, backed up, or read
# on a shared machine years later, so neither may be open-ended.
PORTAL_CONFIRMATION_LINK_SECONDS = 259200  # 72 hours: mail can be slow and people are busy
PORTAL_RESET_LINK_SECONDS = 3600  # 1 hour: it is a password, in transit


CELERY_BEAT_SCHEDULE = {
    "close-deserted-desks": {
        "task": "apps.chat.tasks.close_deserted_desks",
        "schedule": 60.0,
    },
    # Absence is the one state that cannot announce itself: a party who has gone silent sends
    # no event saying so. Every fifteen seconds, so a dropout is acted on close to the grace
    # period rather than up to a minute after it.
    "sweep-interrupted-conversations": {
        "task": "apps.chat.tasks.sweep_interrupted_conversations",
        "schedule": 15.0,
    },
    "sweep-idle-conversations": {
        "task": "apps.chat.tasks.sweep_idle_conversations",
        "schedule": 30.0,
    },
}


# --- one-click sign-in for testing (FR-015 to FR-019) ---
#
# Off by default, because a convenience that is on unless switched off is on in every place
# nobody remembered to switch it off — and what this switches on is signing in as an
# administrator without a password.
#
# It is safe to *have* only because it offers the `seed_demo` accounts, whose passwords are
# already in this repository: it discloses nothing that is not already disclosed. Pointed at a
# real account it would be an authentication bypass outright, which is why the accounts are
# named here rather than found by role.
QUICK_SIGN_IN_ENABLED = False

QUICK_SIGN_IN_ACCOUNTS = {
    "AGENT": "agent@example.com",
    "SUPERVISOR": "supervisor@example.com",
    "ADMINISTRATOR": "admin@example.com",
}
