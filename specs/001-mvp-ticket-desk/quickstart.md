# Quickstart & Validation: MVP Ticket Desk

**Date**: 2026-09-11 | **Plan**: [plan.md](plan.md)

How to run the system locally and prove the MVP works. Scenarios map one-to-one onto the user
stories in [spec.md](spec.md), so a passing run is evidence against the specification rather than a
smoke test.

## Prerequisites

- Python 3.12
- PostgreSQL 16 or later, running locally
- Redis, running locally (Celery broker and rate-limit counter)
- `gettext` installed, for compiling translation catalogs

## Setup

```bash
cp .env.example .env          # then fill in local values; never commit .env
uv sync                       # or: pip install -r requirements/local.txt
python manage.py migrate
python manage.py compilemessages
python manage.py createsuperuser
python manage.py seed_demo    # departments, branches, categories, Arabic and English sample data
```

## Running

Three processes. The worker is not optional: intake confirmation and agent replies are queued, so
without it email silently never sends.

```bash
python manage.py runserver
celery -A config worker -l info
celery -A config beat -l info
```

## Test suite

```bash
pytest                                   # full suite
pytest tests/                            # cross-cutting invariants only
pytest --cov --cov-fail-under=<target>   # coverage gate
ruff check . && ruff format --check . && mypy .
```

The four cross-cutting invariant tests are the ones that must never be skipped, because each maps
directly to a constitutional principle:

| Test | Asserts | Requirement |
|---|---|---|
| `tests/test_scope_isolation.py` | Out-of-scope records return 404, not 403 | FR-023, FR-024 |
| `tests/test_audit_coverage.py` | Every soft-deletable model is registered for audit | FR-027 |
| `tests/test_internal_visibility.py` | No internal message reaches a customer-facing output | FR-015 |
| `tests/test_i18n_completeness.py` | No untranslated user-facing string, no `left`/`right` in CSS | FR-031, FR-032 |

## Validation scenarios

Each scenario is runnable by hand and is also covered by an automated test.

### 1. Intake creates a ticket (User Story 1)
Open `/request/`, submit name, email, subject, and description. **Expect**: a confirmation page
showing a reference of the form `AZM-2026-000001`; a confirmation email in the mail capture; a
contact created with **no organization**; the ticket visible in the agent queue.

### 2. Known contact does not duplicate (User Story 1, SC-003)
Submit the form again with the same email address, different subject. **Expect**: a second ticket,
the **same** contact, no duplicate contact row.

### 3. Agent resolves a ticket (User Story 2)
Sign in as an agent. **Expect**: the queue lists every ticket in the agent's department, not only
their own. Take the ticket, send a reply, then resolve it. **Expect**: the reply appears on the
thread attributed to the agent and in the mail capture; the ticket history shows the assignment,
the message, and the status change with actor and timestamp.

### 4. Concurrent take (edge case, contract 409)
With one ticket unassigned, issue two simultaneous `take` requests as two different agents.
**Expect**: exactly one 200 and one 409.

### 5. Customer reply threads correctly (User Story 2, FR-013)
Reply to the outbound email from the mail capture, preserving headers. **Expect**: the reply lands
on the same ticket, not a new one; a `RESOLVED` ticket returns to `OPEN`;
`InboundMessageLog.match_method` names the rule that matched.

### 6. Organization timeline (User Story 3)
Link the unlinked contact to a new organization, then open the organization. **Expect**: both
tickets appear on one timeline; the link is present in the audit log.

### 7. Scope isolation (User Story 4, FR-024)
As an agent in department A, request a ticket belonging to department B by its exact reference.
**Expect**: **404**, not 403, and nothing in the response revealing the ticket exists.

### 8. Deactivation is immediate (FR-026)
While an agent holds an active session, deactivate the account. **Expect**: their next request is
refused without waiting for the session to expire.

### 9. Audit reconstruction (User Story 5)
Change a ticket's priority, then open `/admin/audit/` filtered to that ticket. **Expect**: an entry
naming actor, UTC timestamp, field, and both values. Attempting to edit or delete it is refused.

### 10. Arabic end to end (User Story 6, SC-007)
Switch to Arabic and repeat scenario 3 with Arabic subject and body. **Expect**: every label and
message in Arabic; `dir="rtl"` on the document; correct right-to-left layout on queue, detail, and
form; Arabic preserved in the outbound email.

### 11. Internal note stays internal (User Story 7, FR-015)
Add an internal note to a ticket, then send a public reply. **Expect**: the note is visible to
staff, visually distinct, and absent from the outbound email including its quoted history.

## Definition of done for any task in this feature

1. A failing test existed before the implementation.
2. Formatter, linter, and type checker pass.
3. New customer-data mutations write an audit entry.
4. New endpoints perform an explicit authorization check and return 404, not 403, out of scope.
5. New user-facing strings exist in both `ar` and `en` catalogs.
6. No secrets or personal data appear in the diff, fixtures, or logs.
7. Migrations are reversible and reviewed separately from application logic.
