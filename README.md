# AZM Customer Support CRM

Bilingual (Arabic/English) support desk. See [docs/roadmap.md](docs/roadmap.md) for the
delivery plan, [specs/001-mvp-ticket-desk/](specs/001-mvp-ticket-desk/) for the current
feature's spec, plan, and tasks, and [docs/decisions/](docs/decisions/) for the architecture
decisions this build follows (Django, PostgreSQL, htmx + Alpine.js, Celery + Redis).

## Status

**Phase One MVP: feature-complete.** All 152 tasks in
[specs/001-mvp-ticket-desk/tasks.md](specs/001-mvp-ticket-desk/tasks.md) are done, with 334
tests passing.

**Not yet ready for real customer data.** Four things remain, none of them code — encryption at
rest, a restore drill, a mail route, and a validation run against the real environment. They are
listed in [docs/production-readiness.md](docs/production-readiness.md).

## Local setup

Requires Python 3.10+ (3.12 recommended — see note below), PostgreSQL 16+, and Redis.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements/local.txt

cp .env.example .env   # fill in real values; .env is gitignored, never commit it

python manage.py migrate
python manage.py compilemessages

# The first administrator, with a department and a branch. Use this rather than
# `createsuperuser`: that command asks only for an email and a name, because those are the
# only fields the model marks required — and it cannot reasonably ask for a department, since
# on an empty database there is none to choose. The account it creates has no scope, so every
# screen filters to nothing and the product looks broken on the first visit. Ask this project
# how it knows.
python manage.py bootstrap_admin \
    --email you@example.com \
    --full-name "Your Name" \
    --department Support \
    --branch "Head Office"

# Creating an account never creates a way in, so set a password before signing in.
python manage.py changepassword you@example.com

python manage.py seed_demo   # departments, branches, categories, demo agent/admin accounts
```

If you already have an administrator with no department or branch, you do not need to start
again: sign in and the screens will say so and offer to set one. That recovery exists because
requiring a second, already-scoped administrator assumes one exists, and on a new installation
none does.

## Running

Three processes. The worker is not optional — outbound email is queued through it, so without
it, confirmation and reply emails are silently never sent.

```bash
python manage.py runserver
celery -A config worker -l info
celery -A config beat -l info
```

## Tests

```bash
pytest -m "not e2e"    # everything except the browser checks
pytest -m e2e          # the browser checks, in their own session
ruff check . && ruff format --check .
mypy .
python manage.py makemigrations --check --dry-run   # fails if a model change has no migration
```

The two must be separate commands. pytest-playwright drives the browser from a greenlet that
owns an event loop, and pytest-asyncio manages its own for the WebSocket consumer tests; run
together they collide with "This event loop is already running".

The `e2e` tests drive a real Chromium through Playwright to verify right-to-left layout —
that the sidebar actually mirrors, that no page overflows sideways, and that the internal
note's warning edge lands on the reading-start side. Those defects are invisible to unit
tests, which can only confirm that `dir="rtl"` is present. Install the browser once with:

```bash
python -m playwright install chromium
```

## A note on this sandbox's environment

This repository was scaffolded and its first slice implemented inside a sandboxed development
session with three real constraints, each documented at the point it mattered rather than
silently worked around:

- **Python 3.10**, not the 3.12 named in [plan.md](specs/001-mvp-ticket-desk/plan.md) — no 3.12
  interpreter was installable without root. Django 5.2 supports 3.10+, so this is a safe
  substitution; install 3.12 in any environment where you can.
- **No PostgreSQL credentials** were available (no working role, no sudo to create one), so the
  automated test suite runs against SQLite (`config/settings/test.py`), which
  [plan.md](specs/001-mvp-ticket-desk/plan.md) already names for local test runs. Local-development
  and production settings (`config/settings/local.py`, `production.py`) target PostgreSQL
  unchanged, per [ADR-002](docs/decisions/002-database.md).
- **No Redis server** was installable, so Celery tasks run in `CELERY_TASK_ALWAYS_EAGER` mode
  under `config.settings.test` — the standard way to test Celery-backed code without a live
  broker, not a change to [ADR-005](docs/decisions/005-background-jobs.md).
- **No outbound network access to CDN hosts** (only PyPI was reachable), so
  `static/js/htmx.min.js` and `static/js/alpine.min.js` are placeholders with a comment
  explaining what to fetch before running the app for real.

None of this affects the design decisions in the ADRs; it affects only how this particular
session verified the code it wrote. A normal development or CI environment with real Postgres,
Redis, and unrestricted network access needs none of these workarounds.

## Documentation

| Document | What it covers |
|---|---|
| [docs/roadmap.md](docs/roadmap.md) | Delivery phases and the MVP cut line |
| [docs/decisions/](docs/decisions/) | Architecture decisions and why |
| [docs/agent-guide.md](docs/agent-guide.md) | One page an agent needs to work a ticket, in English and Arabic |
| [docs/accessibility-review.md](docs/accessibility-review.md) | What is checked automatically, what still needs a person |
| [docs/email-setup.md](docs/email-setup.md) | What to ask IT for so replies reach customers — written to hand over as-is |
| [docs/production-readiness.md](docs/production-readiness.md) | **What must be true before this holds a real customer's data** |
| [specs/001-mvp-ticket-desk/](specs/001-mvp-ticket-desk/) | Specification, plan, contracts and task list |

## Working on the translations

Both catalogs must be complete and free of fuzzy entries — Django silently ignores a fuzzy
translation and falls back to English, so a fuzzy entry is an untranslated one that looks
translated. `tests/test_translation_catalog.py` fails the build on either.

```bash
python manage.py makemessages -l ar -l en --ignore=.venv
python tools/catalog.py status        # what is missing or guessed
python tools/catalog.py sync-english  # English msgstr = its own msgid
python manage.py compilemessages
```

Review every entry `msgmerge` marks fuzzy before clearing the flag. It guesses from similar
strings and has been wrong more often than right on this project — "Action" became "Active",
"Changes" became "Channel", and "Accounts in X" became "All tickets in X".

## What is verified vs. not yet built

The Phase One MVP ships in vertical-slice order (see
[specs/001-mvp-ticket-desk/tasks.md](specs/001-mvp-ticket-desk/tasks.md)). As of this commit:

- **Built and tested** (31 passing tests, `ruff` and `mypy` clean): project skeleton and
  settings; the core base classes (timestamps, soft delete, department/branch scoping); the
  custom `User`/`Department`/`Branch` models with immediate session termination on
  deactivation; deny-by-default authentication middleware; centralized audit registration
  covering every model that needs one; the public intake flow end to end — form validation,
  honeypot and timing-based abuse rejection, contact matching and deduplication, ticket
  reference allocation, and a bilingual confirmation email queued through Celery; a real
  Arabic translation catalog (not a placeholder) covering every string shipped so far.
- **Not yet built**: the agent queue and ticket-resolution screens, inbound email threading,
  the customer/organization timeline UI, the administrator screens beyond Django's built-in
  admin, and the Playwright right-to-left visual checks. These are Phases 4 onward in
  [tasks.md](specs/001-mvp-ticket-desk/tasks.md).
