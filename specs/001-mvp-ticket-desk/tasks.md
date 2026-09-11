---
description: "Task list for MVP Ticket Desk implementation"
---

# Tasks: MVP Ticket Desk

**Input**: Design documents from `specs/001-mvp-ticket-desk/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Test tasks are included and are **not optional**. Constitution Principle I (Test-First)
is marked NON-NEGOTIABLE, so every implementation task is preceded by the test that must fail first.

**Organization**: Tasks are grouped by user story so each story can be implemented, tested, and
demonstrated independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on incomplete work)
- **[Story]**: The user story this task serves (US1–US7)
- Every task names the exact file path it touches

## Path conventions

Paths follow the structure in [plan.md](plan.md): `config/` for project settings, `apps/<name>/` for
feature apps, `templates/`, `static/`, `locale/`, and a top-level `tests/` for cross-cutting
invariants.

## A note on story ordering

The spec prioritizes access control (US4), audit (US5), and bilingual operation (US6) below the
working loop, but the constitution requires their *mechanisms* from the first model. This is
resolved by splitting them: the enforcement machinery lands in Phase 2 (Foundational), while the
user-facing screens and the exhaustive verification stay in their own story phases. No model is ever
written without scoping, audit, and translation already in place.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project skeleton, tooling, and the quality gates the constitution requires.

- [X] T001 Create the directory structure from plan.md: `config/settings/`, `apps/`, `templates/`, `static/`, `locale/`, `tests/`
- [X] T002 Initialize the Python project in `pyproject.toml` with Django 5.2 LTS, `psycopg[binary]`, `celery`, `redis`, `django-htmx`, `django-auditlog`, `django-ratelimit`, pinned to exact versions, and commit the lock file
- [X] T003 [P] Configure `ruff` for linting and formatting in `pyproject.toml`, including a rule banning `left:`/`right:` in favour of logical properties
- [X] T004 [P] Configure `mypy` in `pyproject.toml` with `django-stubs`, set to fail on untyped definitions in `apps/`
- [X] T005 [P] Configure `pytest`, `pytest-django`, `factory_boy`, and coverage reporting in `pyproject.toml` and `conftest.py`
- [X] T006 Split settings into `config/settings/base.py`, `config/settings/local.py`, and `config/settings/production.py`, reading every value from environment variables with no secret defaults
- [X] T007 [P] Create `.env.example` listing every required environment variable with safe placeholder values, and add `.env` to `.gitignore`
- [X] T008 [P] Configure internationalization in `config/settings/base.py`: `LANGUAGES = [("ar", ...), ("en", ...)]`, `LocaleMiddleware`, `USE_I18N`, `USE_TZ = True`, `TIME_ZONE = "UTC"`, and `LOCALE_PATHS`
- [X] T009 [P] Create the Celery application in `config/celery.py` with Redis as broker and result backend, and wire it in `config/__init__.py`
- [X] T010 [P] Vendor htmx 2.x and Alpine.js 3.x into `static/js/` and create `static/css/base.css` using CSS logical properties only
- [X] T011 [P] Create the CI pipeline in `.github/workflows/ci.yml` running `pytest`, `ruff check`, `ruff format --check`, `mypy`, a missing-migrations check, and a dependency vulnerability scan
- [X] T012 Create `templates/base.html` setting `lang` and `dir` on the `html` element from the active locale via `get_language_bidi`

**Checkpoint**: `pytest` runs green on an empty suite in CI, and all quality gates are enforced.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The base classes and middleware that make scoping, auditing, soft deletion, and
deny-by-default structural rather than per-model discipline.

**⚠️ CRITICAL**: No user story work begins until this phase is complete.

**⚠️ ORDERING**: The custom user model in T017 MUST exist before the first migration is generated.
Django cannot switch `AUTH_USER_MODEL` after initial migrations without a destructive reset.

### Tests first

- [X] T013 [P] Write `apps/core/tests/test_models.py` asserting `TimeStampedModel` sets UTC timestamps and `SoftDeleteModel` hides deleted rows from the default manager while `all_objects` returns them
- [X] T014 [P] Write `apps/core/tests/test_querysets.py` asserting `ScopedQuerySet.for_user()` excludes rows outside the user's department and branch
- [X] T015 [P] Write `tests/test_scope_isolation.py` as a self-extending invariant: it discovers every model inheriting `ScopedModel` and asserts an out-of-scope request returns **404, not 403**
- [X] T016 [P] Write `tests/test_audit_coverage.py` asserting every model inheriting `SoftDeleteModel` is registered with `auditlog`
- [X] T017 [P] Write `tests/test_i18n_completeness.py` asserting no user-facing template string sits outside a translation tag and no stylesheet uses `left:` or `right:`
- [X] T018 [P] Write `apps/accounts/tests/test_deactivation.py` asserting a deactivated user's existing session is refused on the next request, not at next sign-in
- [X] T019 [P] Write `apps/core/tests/test_logging_filters.py` asserting known sensitive field names never appear in emitted log records

### Implementation

- [X] T020 Implement `TimeStampedModel`, `SoftDeleteModel`, and `ScopedModel` abstract bases in `apps/core/models.py`, with partial unique index support conditioned on `deleted_at IS NULL`
- [X] T021 Implement `ScopedQuerySet` and `ScopedManager` with `for_user(user)` in `apps/core/querysets.py`
- [X] T022 Implement `Department` and `Branch` models in `apps/accounts/models.py`
- [X] T023 Implement the custom `User` model in `apps/accounts/models.py` with `email` as the sign-in identifier, `role` choices `AGENT` and `ADMINISTRATOR`, `department`, `branch`, `language`, and set `AUTH_USER_MODEL` in `config/settings/base.py`
- [X] T024 Generate and review the initial migrations for `accounts`, then run `migrate` against PostgreSQL
- [X] T025 Actor attribution for web requests is provided by `auditlog.middleware.AuditlogMiddleware` (already in `MIDDLEWARE`); no separate `apps/core/middleware.py` actor middleware was needed — see `apps/core/tasks.py` for the Celery-side equivalent (T026)
- [X] T026 Implement a Celery task base in `apps/core/tasks.py` that requires an explicit actor, so background writes cannot silently attribute human work to a system user
- [X] T027 Enable `LoginRequiredMiddleware` globally in `config/settings/base.py` and mark the intake and sign-in views as the only exemptions
- [X] T028 Implement session invalidation on the `User.is_active` transition in `apps/accounts/models.py`
- [X] T029 Implement `get_object_or_404_for_user()` in `apps/core/shortcuts.py` so the 404-not-403 rule is applied by one helper rather than by convention
- [X] T030 Register `auditlog` in `config/settings/base.py` and create the registration module `apps/core/audit.py`
- [X] T031 Configure structured logging with a PII and secret redaction filter in `config/settings/base.py` and `apps/core/logging.py`
- [X] T032 [P] Implement sign-in, sign-out, and language-switch views in `apps/accounts/views.py` and `apps/accounts/urls.py` per [contracts/http-endpoints.md](contracts/http-endpoints.md)
- [X] T033 [P] Authenticated shell at `templates/shell.html` (a base other pages extend, rather than an include — Django includes cannot wrap a block) with navigation and the language switcher
- [X] T034 Extract and compile the initial translation catalogs into `locale/ar/LC_MESSAGES/` and `locale/en/LC_MESSAGES/`

**Checkpoint**: A user can sign in, the language switcher works, out-of-scope access returns 404,
and the four invariant tests run (passing trivially until models exist).

---

## Phase 3: User Story 1 - Capture an incoming request as a ticket (Priority: P1) 🎯 MVP

**Goal**: A public web form turns a stranger's request into a tracked ticket linked to a contact,
with a quotable reference and a confirmation email.

**Independent Test**: Submit the public form with valid details. A ticket appears in the unassigned
queue, linked to a contact, and a confirmation email carrying the reference is sent.

### Tests for User Story 1

- [X] T035 [P] [US1] Write `apps/intake/tests/test_intake_contract.py` covering the three public endpoints in [contracts/http-endpoints.md](contracts/http-endpoints.md), including that the confirmation page discloses only the reference
- [X] T036 [P] [US1] Write `apps/intake/tests/test_validation.py` asserting incomplete submissions are rejected with field-level errors and entered content is preserved
- [X] T037 [P] [US1] Write `apps/customers/tests/test_contact_matching.py` asserting a known email matches the existing contact and creates no duplicate, and an unknown email creates a contact with **no organization**
- [X] T038 [P] [US1] Write `apps/tickets/tests/test_reference.py` asserting references follow `AZM-{year}-{sequence}`, are unique under concurrency, and never change once assigned
- [X] T039 [P] [US1] Write `apps/intake/tests/test_abuse_protection.py` asserting the honeypot field and rate limit reject automated submissions and that rate limiting fails open when Redis is unavailable
- [X] T040 [P] [US1] Write `apps/intake/tests/test_arabic_intake.py` asserting Arabic subject and description are stored and re-rendered unchanged
- [X] T041 [P] [US1] Write `apps/messaging/tests/test_confirmation_email.py` asserting the confirmation contains the reference and a reply-to address carrying it, in the visitor's language

### Implementation for User Story 1

- [X] T042 [P] [US1] Implement `Organization` in `apps/customers/models.py`, scoped and soft-deletable
- [X] T043 [P] [US1] Implement `Contact` in `apps/customers/models.py` with a **nullable** organization, and `ContactDetail` with a partial unique index on `(kind, value)` where not deleted
- [X] T044 [US1] Implement `Category` and `Ticket` in `apps/tickets/models.py` with the fields and indexes in [data-model.md](data-model.md), including the ticket's own organization reference
- [X] T045 [US1] Implement the reference allocator in `apps/tickets/services/reference.py` using a per-year database sequence
- [X] T046 [US1] Register `Organization`, `Contact`, `ContactDetail`, `Category`, and `Ticket` for audit in `apps/core/audit.py`
- [X] T047 [US1] Generate and review migrations for `customers` and `tickets`
- [X] T048 [US1] Implement contact matching and creation in `apps/customers/services/matching.py`, normalizing email to lower case before lookup
- [X] T049 [US1] Implement the intake form in `apps/intake/forms.py` with the honeypot field and minimum completion-time check
- [X] T050 [US1] Implement the intake views in `apps/intake/views.py` and routes in `apps/intake/urls.py`, wrapping contact and ticket creation in `transaction.atomic`
- [X] T051 [US1] Apply `django-ratelimit` to the intake POST view keyed on client address and submitted email
- [X] T052 [P] [US1] Create `templates/intake/form.html` and `templates/intake/submitted.html` with all strings translated
- [X] T053 [P] [US1] Create bilingual confirmation email templates in `templates/messaging/email/confirmation.{ar,en}.txt`
- [X] T054 [US1] Implement the outbound send task in `apps/messaging/tasks.py` with retry and backoff, and the reply-to token format from [contracts/email.md](contracts/email.md)
- [X] T055 [US1] Add the new models to the invariant registries so `tests/test_scope_isolation.py` and `tests/test_audit_coverage.py` cover them
- [X] T056 [US1] Extract and compile translations for this phase into `locale/ar/LC_MESSAGES/django.po` and `locale/en/LC_MESSAGES/django.po`

**Checkpoint**: Quickstart scenarios 1 and 2 pass. Requests stop being lost.

---

## Phase 4: User Story 2 - Agent resolves a ticket end to end (Priority: P2)

**Goal**: An agent works a ticket from a department-wide queue, replies by email, and resolves it,
with customer replies threading back onto the same ticket.

**Independent Test**: With a ticket in the queue, sign in as an agent, take it, reply, and resolve.
The customer receives the reply and the history shows both events with actor and timestamp.

### Tests for User Story 2

- [X] T057 [P] [US2] Write `apps/tickets/tests/test_queue_contract.py` asserting the queue lists **all** department tickets, paginates, sorts by priority then age, and filters per [contracts/http-endpoints.md](contracts/http-endpoints.md)
- [X] T058 [P] [US2] Write `apps/tickets/tests/test_take_concurrency.py` asserting two simultaneous takes produce exactly one 200 and one 409
- [X] T059 [P] [US2] Write `apps/tickets/tests/test_status_lifecycle.py` asserting permitted transitions succeed and all others return 422
- [X] T060 [P] [US2] Write `apps/tickets/tests/test_field_changes.py` asserting category and priority changes record before and after values on the history
- [X] T061 [P] [US2] Write `apps/tickets/tests/test_reply.py` asserting a reply is queued, appears on the thread attributed to the agent, and returns the thread fragment to htmx callers
- [X] T062 [P] [US2] Write `apps/messaging/tests/test_inbound_threading.py` covering all four threading rules in [contracts/email.md](contracts/email.md) in priority order, including the no-match case creating a new ticket
- [X] T063 [P] [US2] Write `apps/messaging/tests/test_reopen_on_reply.py` asserting an inbound message on a resolved or closed ticket returns it to `OPEN`
- [X] T064 [P] [US2] Write `apps/messaging/tests/test_delivery_failure.py` asserting a permanent send failure is visible on the ticket and the message stays on the thread
- [X] T065 [P] [US2] Write `tests/test_internal_visibility.py` asserting no message with `visibility=INTERNAL` appears in any customer-facing output, including quoted email history

### Implementation for User Story 2

- [X] T066 [US2] Implement `Message` in `apps/tickets/models.py` with `direction`, `visibility`, `channel`, `delivery_status`, `delivery_error`, and `external_id`
- [X] T067 [US2] Implement `InboundMessageLog` in `apps/messaging/models.py` with `match_method` and `processing_error`
- [X] T068 [US2] Implement the status lifecycle and transition guard in `apps/tickets/services/lifecycle.py`
- [X] T069 [US2] Generate and review migrations for `tickets` and `messaging`
- [X] T070 [US2] Implement the queue view with filters in `apps/tickets/views.py`, using `for_user()` and returning list fragments for htmx requests
- [X] T071 [US2] Implement the ticket detail view with thread, customer context, and history in `apps/tickets/views.py`
- [X] T072 [US2] Implement the `take` endpoint with a row-level lock returning 409 when already assigned, in `apps/tickets/views.py`
- [X] T073 [US2] Implement the status and field-change endpoints in `apps/tickets/views.py`
- [X] T074 [US2] Implement the public reply endpoint in `apps/tickets/views.py`, queueing the outbound message and returning the appended thread fragment
- [X] T075 [US2] Implement inbound ingestion in `apps/messaging/services/inbound.py` applying the four threading rules and recording `match_method`
- [X] T076 [US2] Inbound collection task seam in `apps/messaging/tasks.py`; the adapter itself (provider webhook vs IMAP) is blocked on ADR-006 and raises explicitly rather than pretending to poll — `services/inbound.py` is fully tested independently of transport
- [X] T077 [US2] Implement delivery-status callbacks and failure surfacing in `apps/messaging/services/outbound.py`
- [X] T078 [P] [US2] Create `templates/tickets/queue.html` and `templates/tickets/partials/queue_list.html`
- [X] T079 [P] [US2] Create `templates/tickets/detail.html` with thread, history, and reply form, plus `templates/tickets/partials/thread.html`
- [X] T080 [P] [US2] Create bilingual agent reply email templates in `templates/messaging/email/reply.{ar,en}.txt`, filtering on `visibility=PUBLIC`
- [X] T081 [US2] Register `Message` for audit and add it to the invariant registries
- [X] T082 [US2] Extract and compile translations for this phase into `locale/ar/LC_MESSAGES/django.po` and `locale/en/LC_MESSAGES/django.po`

**Checkpoint**: Quickstart scenarios 3, 4, 5, and 11 pass. The core support loop works.

---

## Phase 5: User Story 3 - Maintain customer organizations, contacts, and history (Priority: P3)

**Goal**: Staff see an organization, its people, every ticket any of them raised, and the notes held
against it, and can link contacts that arrived without an employer.

**Independent Test**: Link an unlinked contact to a new organization, then open the organization and
see both of its tickets and a note on one timeline.

### Tests for User Story 3

- [ ] T083 [P] [US3] Write `apps/customers/tests/test_organization_views.py` covering the customer endpoints in [contracts/http-endpoints.md](contracts/http-endpoints.md)
- [ ] T084 [P] [US3] Write `apps/customers/tests/test_timeline.py` asserting the organization timeline combines tickets from every contact with notes in reverse chronological order, and narrows correctly to one contact
- [ ] T085 [P] [US3] Write `apps/customers/tests/test_contact_linking.py` asserting linking an unlinked contact moves its tickets onto the organization timeline and is audited
- [ ] T086 [P] [US3] Write `apps/customers/tests/test_contact_move.py` asserting moving a contact between organizations leaves each existing ticket's own organization reference unchanged
- [ ] T087 [P] [US3] Write `apps/customers/tests/test_soft_delete.py` asserting a deleted organization disappears from listings, stays recoverable, is audited, and does not block reuse of its contacts' email addresses
- [ ] T088 [P] [US3] Write `apps/customers/tests/test_empty_states.py` asserting an organization with no tickets renders an explanatory empty timeline

### Implementation for User Story 3

- [ ] T089 [US3] Implement `Note` in `apps/customers/models.py`, scoped and soft-deletable, and generate its migration
- [ ] T090 [US3] Implement the timeline aggregation service in `apps/customers/services/timeline.py`, paginated and indexed for the SC-009 volumes
- [ ] T091 [US3] Implement organization list, detail, timeline, edit, and note endpoints in `apps/customers/views.py`
- [ ] T092 [US3] Implement the unlinked contacts list and the contact link endpoint in `apps/customers/views.py`
- [ ] T093 [US3] Implement contact and contact-detail editing, and administrator soft deletion, in `apps/customers/views.py`
- [ ] T094 [P] [US3] Create `templates/customers/list.html`, `detail.html`, `unlinked.html`, and `templates/customers/partials/timeline.html`
- [ ] T095 [US3] Register `Note` for audit, add it to the invariant registries, then extract and compile translations for this phase

**Checkpoint**: Quickstart scenario 6 passes. Context is available to agents.

---

## Phase 6: User Story 4 - Administrator controls who can see and do what (Priority: P4)

**Goal**: Administrators manage staff accounts and scope, and the system refuses everything that is
not explicitly permitted.

**Independent Test**: As an agent in department A, request a ticket in department B by its exact
reference. The response is 404 and reveals nothing.

### Tests for User Story 4

- [ ] T096 [P] [US4] Extend `tests/test_scope_isolation.py` to cover every model shipped in Phases 3 to 5, asserting 404 rather than 403
- [ ] T097 [P] [US4] Write `apps/accounts/tests/test_role_enforcement.py` asserting an agent attempting an administrator action receives 403 and the attempt is recorded
- [ ] T098 [P] [US4] Write `apps/accounts/tests/test_anonymous_access.py` asserting every non-public path redirects an unauthenticated visitor to sign-in
- [ ] T099 [P] [US4] Write `apps/accounts/tests/test_user_management.py` asserting a created account has exactly one role, at least one department, and cannot sign in until a password is set
- [ ] T100 [P] [US4] Write `apps/accounts/tests/test_scope_assignment.py` asserting changing a user's department or branch changes what they can reach, and is audited

### Implementation for User Story 4

- [ ] T101 [US4] Implement user creation, listing, and scope reassignment views in `apps/accounts/views.py`
- [ ] T102 [US4] Implement the deactivation endpoint in `apps/accounts/views.py`, terminating active sessions
- [ ] T103 [US4] Implement the administrator role requirement as a view mixin in `apps/accounts/permissions.py`, recording refused attempts
- [ ] T104 [US4] Audit every view added in Phases 3 to 5 and confirm each reads through `for_user()` or `get_object_or_404_for_user()`, fixing any that do not
- [ ] T105 [P] [US4] Create `templates/accounts/users.html` and `templates/accounts/user_form.html`
- [ ] T106 [US4] Register `User`, `Department`, and `Branch` for audit, then extract and compile translations for this phase

**Checkpoint**: Quickstart scenarios 7 and 8 pass. Nothing is reachable by default.

---

## Phase 7: User Story 5 - Every change is auditable (Priority: P5)

**Goal**: An administrator can reconstruct who changed what, when, and from what value.

**Independent Test**: Change a ticket's priority, filter the audit log to that ticket, and read back
actor, UTC timestamp, field, and both values. Editing the entry is refused.

### Tests for User Story 5

- [ ] T107 [P] [US5] Write `apps/core/tests/test_audit_content.py` asserting entries capture actor, UTC timestamp, entity, action, and before and after values for each changed field
- [ ] T108 [P] [US5] Write `apps/core/tests/test_audit_immutability.py` asserting no role, including administrator, can edit or delete an audit entry
- [ ] T109 [P] [US5] Write `apps/core/tests/test_audit_filters.py` asserting the log filters correctly by entity, actor, and date range
- [ ] T110 [P] [US5] Write `apps/core/tests/test_audit_redaction.py` asserting audit entries never store credentials or secret material in readable form
- [ ] T111 [P] [US5] Write `apps/core/tests/test_background_actor.py` asserting a Celery task writing to a customer record records the initiating human, not a system user

### Implementation for User Story 5

- [ ] T112 [US5] Implement the audit log view with entity, actor, and date filters in `apps/core/views.py`, read-only and administrator-only
- [ ] T113 [P] [US5] Create `templates/core/audit_log.html` with filters and pagination
- [ ] T114 [US5] Enforce immutability in `apps/core/admin.py` by registering the audit model read-only and removing any update or delete path, then compile translations into `locale/*/LC_MESSAGES/django.po`

**Checkpoint**: Quickstart scenario 9 passes. Disputes are answerable from evidence.

---

## Phase 8: User Story 6 - Work in Arabic or English (Priority: P6)

**Goal**: The entire MVP is usable in Arabic with correct right-to-left layout, and in English.

**Independent Test**: Switch to Arabic and complete the full agent flow. Every label, message, date,
and control renders in Arabic, right to left.

### Tests for User Story 6

- [ ] T115 [P] [US6] Extend `tests/test_i18n_completeness.py` to fail on any untranslated user-facing string across every template shipped so far
- [ ] T116 [P] [US6] Write `tests/e2e/test_rtl_layout.py` using Playwright to assert `dir="rtl"` and correct layout on the queue, ticket detail, customer detail, and intake form
- [ ] T117 [P] [US6] Write `apps/accounts/tests/test_language_persistence.py` asserting the language choice survives reload and subsequent sign-ins
- [ ] T118 [P] [US6] Write `apps/core/tests/test_formatting.py` asserting dates, times, and numbers format per the active language
- [ ] T119 [P] [US6] Write `apps/messaging/tests/test_email_language.py` asserting outbound email uses the contact's recorded language, defaulting to Arabic when unknown
- [ ] T120 [P] [US6] Write `apps/tickets/tests/test_mixed_script.py` asserting Arabic ticket content renders correctly inside the English interface

### Implementation for User Story 6

- [ ] T121 [US6] Complete the Arabic translation catalog in `locale/ar/LC_MESSAGES/django.po` for every string in the MVP, including plural forms
- [ ] T122 [US6] Complete the English catalog in `locale/en/LC_MESSAGES/django.po`
- [ ] T123 [US6] Fix every right-to-left layout defect found by T116 in `static/css/base.css` and the affected templates, using logical properties only
- [ ] T124 [US6] Implement locale-aware date, time, and number formatting helpers in `apps/core/templatetags/formatting.py`
- [ ] T125 [US6] Implement recipient-language selection for outbound email in `apps/messaging/services/outbound.py`
- [ ] T126 [P] [US6] Add Arabic content to the `seed_demo` fixtures in `apps/core/management/commands/seed_demo.py` so encoding and direction problems surface in every test run

**Checkpoint**: Quickstart scenario 10 passes. SC-007 is verifiable rather than an opinion.

---

## Phase 9: User Story 7 - Internal messages never reach the customer (Priority: P7)

**Goal**: A staff-only message is visible to staff, visually distinct, and absent from every
customer-facing output.

**Independent Test**: Add an internal note, send a public reply, and confirm the note appears in no
customer-facing output including quoted email history.

### Tests for User Story 7

- [ ] T127 [P] [US7] Extend `tests/test_internal_visibility.py` to enumerate every customer-facing output path and assert none can emit an internal message
- [ ] T128 [P] [US7] Write `apps/tickets/tests/test_internal_note_endpoint.py` covering the internal note endpoint in [contracts/http-endpoints.md](contracts/http-endpoints.md)
- [ ] T129 [P] [US7] Write `apps/messaging/tests/test_quoted_history.py` asserting quoted history in outbound email contains public messages only
- [ ] T130 [P] [US7] Write `apps/tickets/tests/test_thread_distinction.py` asserting internal and public messages are unambiguously distinct in the rendered thread

### Implementation for User Story 7

- [ ] T131 [US7] Implement the internal note endpoint in `apps/tickets/views.py`
- [ ] T132 [US7] Implement a single customer-facing message filter in `apps/tickets/services/visibility.py` and route every customer-facing path through it
- [ ] T133 [P] [US7] Update `templates/tickets/partials/thread.html` to render internal messages distinctly, using more than colour alone
- [ ] T134 [US7] Extract and compile translations for this phase into `locale/ar/LC_MESSAGES/django.po` and `locale/en/LC_MESSAGES/django.po`

**Checkpoint**: The privacy boundary live chat will depend on is in place and proven.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Performance, accessibility, operational readiness, and the decisions that block release
rather than development.

- [ ] T135 [P] Add database indexes and verify queue and timeline response times against a seeded dataset of 50,000 tickets and 10,000 organizations per SC-009, in `apps/tickets/migrations/` and `apps/customers/migrations/`
- [ ] T136 [P] Profile and remove N+1 queries in `apps/tickets/views.py` and `apps/customers/services/timeline.py`, asserted by query-count tests in `tests/test_query_budget.py`
- [ ] T137 [P] Write `tests/test_concurrent_agents.py` exercising the assumed 50 concurrent agents from [research.md](research.md#8-scale-assumptions)
- [ ] T138 [P] Run an accessibility pass over `templates/` in both languages, covering keyboard navigation and screen-reader labels, and record findings in `docs/accessibility-review.md`
- [ ] T139 [P] Verify mobile browser layout for every screen in `templates/` per FR-036, fixing defects in `static/css/base.css`
- [ ] T140 [P] Write the one-page agent guide referenced by SC-008 in `docs/agent-guide.md`, in Arabic and English
- [ ] T141 [P] Document local setup and the three required processes in `README.md`, matching [quickstart.md](quickstart.md)
- [ ] T142 Set the coverage threshold in CI and record the agreed figure in `pyproject.toml`
- [ ] T143 Complete [ADR-006](../../docs/decisions/006-deployment-target.md) with the deployment target, then move ADR-002 and ADR-005 from `Proposed` to `Accepted` or revise them
- [ ] T144 Configure encryption of personal data at rest per the decided deployment target and record the mechanism in `docs/operations.md`, satisfying constitution Principle III
- [ ] T145 Provision the outbound reply-to address and inbound mail route from [contracts/email.md](contracts/email.md), configure them in `config/settings/production.py`, then re-run `apps/messaging/tests/` against a real mailbox
- [ ] T146 Exercise database backup and restore end to end and record the procedure in `docs/operations.md`
- [ ] T147 Confirm the assumed status lifecycle and priority values with stakeholders, updating `apps/tickets/models.py` and [data-model.md](data-model.md) with a migration if they differ
- [ ] T148 Run all eleven validation scenarios in [quickstart.md](quickstart.md) in both languages before release, recording results in `docs/release-checklist.md`

---

## Dependencies

### Phase order

```text
Phase 1 Setup
   └─▶ Phase 2 Foundational  ◀── blocks everything
          ├─▶ Phase 3 US1 (P1)  🎯 MVP boundary
          │      └─▶ Phase 4 US2 (P2)   needs tickets and contacts from US1
          │             ├─▶ Phase 5 US3 (P3)   needs tickets for the timeline
          │             └─▶ Phase 9 US7 (P7)   needs the Message model from US2
          ├─▶ Phase 6 US4 (P4)   extends scope tests across shipped models
          ├─▶ Phase 7 US5 (P5)   audits models shipped in earlier phases
          └─▶ Phase 8 US6 (P6)   translates screens shipped in earlier phases
                 └─▶ Phase 10 Polish
```

### Hard ordering constraints

1. **T023 before T024**: the custom user model must exist before the first migration. Django cannot
   change `AUTH_USER_MODEL` afterwards without a destructive reset.
2. **T020 and T021 before any feature model**: every scoped, audited, soft-deletable entity inherits
   these bases. Writing a model first means rewriting it.
3. **US1 before US2**: tickets and contacts must exist before an agent can work one.
4. **US2 before US7**: the `Message` model carries the visibility field.
5. **US4, US5, and US6 after the models they verify**: each extends an invariant test across
   everything shipped so far, so running them earlier proves less.
6. **T143 before T144 and T146**: encryption at rest and the backup procedure are properties of a
   deployment target that has not been chosen.

### Story independence

US1 delivers value alone: requests are captured instead of lost. US2 requires US1 for input. US3,
US4, US5, US6, and US7 each deepen what already exists and can be reordered among themselves to suit
the team, with the caveat in constraint 5.

## Parallel execution examples

**Phase 1**: T003, T004, T005, T007, T008, T009, T010, T011 all touch different files and can run
together after T001 and T002.

**Phase 2 tests**: T013 through T019 are seven independent test files, all writable in parallel
before any implementation begins.

**Phase 3**: the seven test tasks T035 to T041 run in parallel; then T042 and T043 in parallel;
then T052 and T053 in parallel with the view work.

**Phase 4**: the nine test tasks T057 to T065 run in parallel. Templates T078, T079, and T080 are
independent of each other.

**Phase 10**: T135 through T141 are all independent.

## Implementation strategy

**Minimum demonstrable increment**: Phases 1, 2, and 3. That is a public form that reliably captures
requests into a scoped, audited, bilingual system. It is worth deploying internally on its own.

**First genuinely useful release**: add Phase 4. An agent can now resolve a ticket end to end, which
is the sentence the whole MVP is defined by.

**Release candidate**: Phases 5 through 9, then Phase 10. Note that T143 to T146 are release
blockers that do not block development, so they should be started early in parallel rather than
discovered at the end.

**Task total**: 148. Setup 12, Foundational 22, US1 22, US2 26, US3 13, US4 11, US5 8, US6 12,
US7 8, Polish 14.
