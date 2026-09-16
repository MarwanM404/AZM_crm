# AZM Customer Support CRM

A bilingual (Arabic / English) customer support desk: ticketing, live chat, and a customer
portal. Right-to-left throughout, not as a translation layer over an English product.

Built with Django 5.2, PostgreSQL, htmx + Alpine.js, Channels over ASGI, and Celery + Redis.
The reasoning behind each of those is in [docs/decisions/](docs/decisions/).

## What it does

- **Ticket desk** — public request form, inbound email threading, an agent queue with
  department/branch scoping, internal notes, and an immutable audit trail.
- **Live chat** — real-time conversations over WebSockets, with supervisor observation and
  private coaching the customer never sees.
- **Customer portal** — customers create an account, prove their address, read their own
  requests, reply, and raise new ones.
- **Bilingual everywhere** — every screen and every outbound email, in Arabic and English,
  including the six Arabic plural forms.

## Status

Four specifications are complete and merged.

| Spec | What it added | Tasks |
|---|---|---|
| [001-mvp-ticket-desk](specs/001-mvp-ticket-desk/) | The desk: intake, queue, scoping, audit, email | 152 / 152 |
| [002-live-chat](specs/002-live-chat/) | Real-time chat, supervision, whisper | 134 / 134 |
| [003-fix-admin-and-signin](specs/003-fix-admin-and-signin/) | Administration screens, the sign-in page, bilingual fixes | 75 / 75 |
| [004-customer-portal](specs/004-customer-portal/) | Customer accounts, self-service | 96 / 96 |

**1,107 tests** plus **122 browser tests**, at 93.7% coverage. Every check the portal added has
been demonstrated to fail against the defect it guards — see
[the mutation record](specs/004-customer-portal/quickstart.md).

### Not yet ready for real customer data

Eight items, none of them code, in
[docs/production-readiness.md](docs/production-readiness.md). Two block the portal outright:

- **A mail route.** [docs/email-setup.md](docs/email-setup.md) is written to hand to IT as-is.
  Without delivery nobody can create a portal account at all — registration, confirmation and
  password reset are entirely email, by design, because an address nobody has proved is worth
  nothing.
- **An Arabic reading pass.** Six portal screens and four emails. The catalogs report complete,
  which means *present*, not correct: every Arabic string was written during implementation and
  read back by nobody who speaks it first.

## Quick start

Requires Python 3.12 (3.10+ works), PostgreSQL 16+, and Redis.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements/local.txt

cp .env.example .env   # fill in real values; .env is gitignored, never commit it

python manage.py migrate
python manage.py compilemessages
```

Then create the first administrator. Use `bootstrap_admin`, **not** `createsuperuser`: the
latter asks only for an email and a name, because those are the only fields the model marks
required — and it cannot reasonably ask for a department, since on an empty database there is
none to choose. The account it creates has no scope, so every screen filters to nothing and the
product looks broken on the first visit.

```bash
python manage.py bootstrap_admin \
    --email you@example.com \
    --full-name "Your Name" \
    --department Support \
    --branch "Head Office"

# Creating an account never creates a way in, so set a password before signing in.
python manage.py changepassword you@example.com

python manage.py seed_demo   # departments, branches, categories, demo accounts
```

Already have an administrator with no department or branch? You do not need to start again:
sign in, and the screens say so and offer to set one. That recovery exists because requiring a
second, already-scoped administrator assumes one exists, and on a new installation none does.

## Running

Three processes. The worker is not optional — outbound email is queued through it, so without
it confirmation and reply emails are silently never sent.

```bash
python manage.py runserver     # ASGI via daphne, so WebSockets work in development
celery -A config worker -l info
celery -A config beat -l info
```

## Tests

```bash
pytest -m "not e2e" --cov   # everything except the browser checks
pytest -m e2e               # the browser checks, in their own session
ruff check . && ruff format --check .
mypy .
python manage.py makemigrations --check --dry-run   # fails if a model change has no migration
```

**The two pytest runs must be separate commands.** pytest-playwright drives the browser from a
greenlet that owns an event loop, and pytest-asyncio manages its own for the WebSocket consumer
tests; run together they collide with "This event loop is already running".

The browser tests drive a real Chromium to check what no unit test can see: that the layout
actually mirrors in Arabic rather than merely carrying `dir="rtl"`, that no page overflows
sideways on a phone, that a form error is announced to a screen reader, and that a customer's
page never contains an internal note. Install the browser once:

```bash
python -m playwright install chromium
```

### Proving the tests would notice

```bash
python tools/mutate.py
```

Breaks each guarantee the customer portal makes in turn, runs the tests, restores the file, and
refuses to report anything if a patch did not match — a mutation that fails to apply reports
the codebase as perfectly defended. A suite that has never been seen to fail is a suite nobody
has tested.

## How a development machine differs from CI

Neither difference changes a design decision; both change what gets verified where.

| | Local | CI |
|---|---|---|
| Database | SQLite (`config/settings/test.py`) | PostgreSQL 16 (`config/settings/ci.py`) |
| Celery | `CELERY_TASK_ALWAYS_EAGER` | the same, with Redis available |

One test is **skipped on SQLite and only ever runs in CI**: the concurrent-take race needs
`SELECT … FOR UPDATE`, which SQLite does not have. If you change ticket assignment, that
guarantee is checked in CI and nowhere else.

Local development and production settings (`config/settings/local.py`, `production.py`) both
target PostgreSQL, per [ADR-002](docs/decisions/002-database.md).

## Translations

Both catalogs, in both gettext domains, must be complete and free of fuzzy entries. Django
silently ignores a fuzzy translation and falls back to English, so a fuzzy entry is an
untranslated one that looks translated.

```bash
python manage.py makemessages -a --ignore=.venv
python tools/catalog.py status         # what is missing or guessed, per domain
python tools/catalog.py placeholders   # translations that add or drop a placeholder
python tools/catalog.py sync-english   # English msgstr = its own msgid
python manage.py compilemessages
```

Two domains, not one: `django` holds strings from Python and templates, `djangojs` holds the
ones the browser asks for. Checking only the first is how "Online" and "Offline" stayed English
on an otherwise Arabic screen.

**Review every entry `msgmerge` marks fuzzy before clearing the flag.** It guesses from similar
strings and has been wrong far more often than right here — "Action" became "Active", "Changes"
became "Channel", and "I already have an account" became "إنشاء الحساب", *create the account*,
the opposite instruction, on a sign-in page.

`placeholders` is not optional politeness. A guess merged from an unrelated string once carried
`%(size)s` into a message that never supplies it — which is a crash at render time, in Arabic
only, on an error path.

## Documentation

| Document | What it covers |
|---|---|
| [docs/roadmap.md](docs/roadmap.md) | Delivery phases and the MVP cut line |
| [docs/decisions/](docs/decisions/) | The eight architecture decisions, and why |
| [docs/agent-guide.md](docs/agent-guide.md) | What an agent needs to work a ticket, in English and Arabic |
| [docs/email-setup.md](docs/email-setup.md) | What to ask IT for — written to hand over as-is |
| [docs/production-readiness.md](docs/production-readiness.md) | **What must be true before this holds real customer data** |
| [docs/accessibility-review.md](docs/accessibility-review.md) | What is checked automatically, what still needs a person |
| [docs/operations.md](docs/operations.md) | Running it |
| [specs/](specs/) | Specifications, plans, contracts and task lists |

## How this is built

Spec-driven: constitution → specification → plan → tasks → implementation, one feature at a
time, with the architecture decisions recorded as ADRs as they are made. Each specification
directory holds its own `spec.md`, `plan.md`, `tasks.md` and `quickstart.md`.

Tests are written first and **seen to fail for the right reason** before the code that satisfies
them — the project constitution makes that non-negotiable, and `tools/mutate.py` exists because
a test nobody has watched fail is a claim, not a check.
