# Implementation Plan: MVP Ticket Desk

**Branch**: `001-mvp-ticket-desk` | **Date**: 2026-09-11 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-mvp-ticket-desk/spec.md`

## Summary

Deliver the Phase One MVP: a bilingual support desk where a public web form creates a ticket
against a customer organization and contact, an agent works that ticket from a department-wide
queue and replies by email, and every change lands in an immutable audit trail.

The approach is a single server-rendered Django application. Interactivity is provided by htmx
fragments served from ordinary Django views, with Alpine.js for local widget state. Background work
runs on Celery with Redis. Authorization is deny-by-default at the middleware layer and scoped by
department and branch at the queryset layer. Internationalization uses Django's `gettext` for both
screens and email, so a single catalog covers every user-visible string.

These choices are recorded in [ADR-001](../../docs/decisions/001-web-framework.md) through
[ADR-005](../../docs/decisions/005-background-jobs.md).

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: Django 5.2 LTS, `django-htmx`, htmx 2.x, Alpine.js 3.x,
`django-auditlog`, Celery 5.x, `redis`, `psycopg` 3.x, `django-ratelimit`

**Storage**: PostgreSQL 16 or later (ADR-002, `Proposed`). SQLite for local test runs only.

**Testing**: `pytest` with `pytest-django`, `factory_boy` for fixtures, Playwright for the bilingual
and right-to-left end-to-end checks that SC-007 requires

**Target Platform**: Linux server. Specific host NEEDS CLARIFICATION — see
[ADR-006](../../docs/decisions/006-deployment-target.md)

**Project Type**: Web application, server-rendered monolith with background workers

**Performance Goals**: Ticket list and customer timeline remain responsive at 50,000 tickets and
10,000 customers (SC-009). Agent reaches a first reply within 60 seconds of opening the queue
(SC-002), which is an interaction-count target as much as a latency one.

**Constraints**: Arabic and English on every screen and email with correct right-to-left layout;
deny-by-default authorization with no disclosure of out-of-scope records; an audit entry for every
write; soft deletion by default; no secrets or personal data in logs

**Scale/Scope**: Single branch at launch with the model supporting several. Assumed 50 concurrent
agents, 3 departments, roughly 25 screens in the MVP. Agent population NEEDS CLARIFICATION — see
[research.md](research.md).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

### I. Test-First (NON-NEGOTIABLE)

| Requirement | How this plan satisfies it |
|---|---|
| Test precedes implementation | `/speckit-tasks` orders every implementation task behind its test task. No task writes a model or view before its failing test exists. |
| Contract test per public surface | [contracts/](contracts/) enumerates every HTTP endpoint and email behaviour; each gets a contract test. |
| Regression test per bug fix | Enforced at review, recorded in the definition of done in [quickstart.md](quickstart.md). |

**Status**: PASS

### II. Data Integrity & Auditability

| Requirement | How this plan satisfies it |
|---|---|
| Schema validation at the boundary | Django forms validate every write path, including the public intake form. |
| Audit entry on every mutation | `django-auditlog` registered on all customer-facing models, actor supplied by middleware and explicitly by Celery tasks. |
| Soft deletion by default | `SoftDeleteModel` base with a default manager that excludes deleted rows. |
| Transactions for multi-step writes | Intake and reply flows wrapped in `transaction.atomic`. |
| Reversible migrations | Django migrations, reviewed separately per the constitution. |

**Status**: PASS

### III. Security & Access Control

| Requirement | How this plan satisfies it |
|---|---|
| Deny by default | `LoginRequiredMiddleware` globally, with the intake form and sign-in as the only explicit exemptions. |
| Least privilege | Two fixed roles, Agent and Administrator. No user-configurable permissions in the MVP. |
| Secrets outside the repository | All configuration from environment variables; no secret defaults in settings. |
| PII encrypted in transit and at rest | TLS terminated at the edge. Encryption at rest depends on the deployment target and is tracked as an open risk below. |
| No PII or secrets in logs | Logging filters plus a test asserting known sensitive field names never appear in log output. |
| Parameterized queries | ORM throughout. Raw SQL requires review justification. |
| Pinned dependencies | Lock file committed; vulnerability scanning in CI. |

**Status**: PASS with one tracked risk — encryption at rest is unresolvable until ADR-006 is
decided. It is a deployment configuration, not application code, so it does not block Phase 1
design, but it does block production release.

### IV. Simplicity & YAGNI

Every dependency added beyond the framework is justified against a specific requirement:

| Dependency | Justified by | Simpler alternative rejected because |
|---|---|---|
| `django-htmx` | FR-010, FR-011 partial updates | Full page reloads on every filter change harm SC-002 |
| Alpine.js | Local widget state | Hand-written DOM code repeats across screens |
| `django-auditlog` | FR-027 to FR-030 | A hand-rolled audit layer is the exact wheel this library is |
| Celery and Redis | FR-006, FR-013, FR-016 | Cron lacks retries and failure visibility; see ADR-005 |
| `django-ratelimit` | FR-006 | Per-process counters are wrong behind multiple workers |
| Playwright | SC-007 | Right-to-left layout defects are not detectable in unit tests |

No speculative abstraction is introduced. There is no plugin layer, no channel abstraction beyond
the two channels the MVP actually ships, and no configurable permission system.

**Status**: PASS

## Project Structure

### Documentation (this feature)

```text
specs/001-mvp-ticket-desk/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── http-endpoints.md
│   └── email.md
├── checklists/
│   └── requirements.md
├── spec.md
└── tasks.md             # Created later by /speckit-tasks
```

### Source Code (repository root)

```text
config/                      # Django project: settings, urls, asgi, wsgi, celery app
├── settings/
│   ├── base.py
│   ├── local.py
│   └── production.py
└── urls.py

apps/
├── core/                    # Cross-cutting base classes used by every other app
│   ├── models.py            # TimeStampedModel, SoftDeleteModel, ScopedModel
│   ├── querysets.py         # ScopedQuerySet.for_user()
│   ├── middleware.py        # Current-actor middleware for audit attribution
│   └── templatetags/
├── accounts/                # User, Role, Department, Branch, authentication views
├── customers/               # Organization, Contact, ContactDetail, Note
├── tickets/                 # Ticket, Message, Category, status lifecycle, agent queue
├── messaging/               # Outbound email, inbound email ingestion, delivery status
└── intake/                  # Public request form, rate limiting, confirmation

templates/
├── base.html                # Sets dir and lang from the active locale
├── components/              # Shared partials
└── <app>/
    └── partials/            # htmx fragment templates

static/
├── css/                     # Logical properties only; no left/right
└── js/                      # htmx, Alpine, minimal project script

locale/
├── ar/LC_MESSAGES/
└── en/LC_MESSAGES/

tests/                       # Cross-cutting invariants that span apps
├── test_scope_isolation.py  # FR-023, FR-024
├── test_audit_coverage.py   # FR-027
├── test_internal_visibility.py  # FR-015
└── test_i18n_completeness.py    # FR-031

apps/<app>/tests/            # Unit and integration tests owned by each app
```

**Structure Decision**: A single Django project with feature apps under `apps/`. There is no
separate frontend project, because ADR-003 renders the interface from Django templates. Tests live
beside the app that owns them, except for four cross-cutting invariants that must hold across every
app; those live in a top-level `tests/` package so that no single app can quietly exempt itself from
them. The `core` app holds the base model classes every scoped, audited, soft-deletable entity
inherits, which is how FR-020, FR-023, and FR-027 are enforced structurally rather than per model.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Celery and Redis as MVP infrastructure | FR-013 inbound email collection, FR-016 outbound retry with failure visibility, FR-006 shared rate-limit counter | Cron with management commands has no retry, no backoff, and poor failure visibility. Redis is additionally required by live chat immediately after the MVP, so the lighter queue would become a second mechanism rather than a saving. See ADR-005. |

No other constitutional deviation is taken. The encryption-at-rest gap under Principle III is an
open deployment risk rather than a design deviation, and is tracked in
[research.md](research.md#open-deployment-dependency).

## Post-Design Constitution Re-Check

*Re-evaluated after Phase 1 design artifacts were produced.*

| Principle | Result | Evidence from the design |
|---|---|---|
| I. Test-First | PASS | Every contract row in [contracts/](contracts/) is a test. [quickstart.md](quickstart.md) states the definition of done, with a failing test first. |
| II. Data Integrity & Auditability | PASS | [data-model.md](data-model.md) puts audit, soft delete, and scoping in shared base classes, and `tests/test_audit_coverage.py` fails when a model escapes registration. |
| III. Security & Access Control | PASS with tracked risk | Contracts fix the 404-not-403 rule for out-of-scope records, so FR-024 is a test rather than an opinion. Encryption at rest remains blocked on ADR-006 and blocks production release, not design. |
| IV. Simplicity & YAGNI | PASS | The design added no abstraction beyond what a requirement names. `InboundMessageLog` is the only entity not directly in the spec; it exists because FR-013 threading failures are otherwise undiagnosable. |

**Design decisions that tightened requirements**

- Out-of-scope records return **404, not 403**. A 403 confirms existence and would defeat FR-024.
- `Contact.organization` and `Ticket.organization` are both nullable, and the ticket keeps its own
  reference rather than reading through the contact, so FR-042 holds when a contact moves.
- Unique constraints are partial indexes conditioned on `deleted_at IS NULL`, without which a
  soft-deleted record would permanently block reuse of its email address.
- Sessions are invalidated on the `is_active` transition, because checking at next sign-in would not
  satisfy FR-026.

**Gate result**: PASS. Ready for `/speckit-tasks`.
