# Phase 1 Data Model: MVP Ticket Desk

**Date**: 2026-09-11 | **Plan**: [plan.md](plan.md) | **Spec**: [spec.md](spec.md)

Entities are grouped by owning app. Every entity inherits the base behaviour described first.

## Base behaviour

Three abstract bases in `apps/core`, composed as needed:

- **TimeStampedModel**: `created_at`, `updated_at`, both UTC. Applied to every entity.
- **SoftDeleteModel**: `deleted_at`, `deleted_by`. Default manager excludes deleted rows;
  `all_objects` exposes them for administrative recovery. Satisfies FR-020.
- **ScopedModel**: `department` and `branch` foreign keys, both required and set at creation.
  Exposes `objects.for_user(user)`. Satisfies FR-023 and FR-024, per ADR-004.

Unique constraints on soft-deletable models are partial indexes conditioned on
`deleted_at IS NULL`, so a deleted record does not block reuse of its natural key.

## accounts

### Department
Organizational unit that scopes visibility.
`name` (translatable), `is_active`.

### Branch
Location that scopes visibility. One row at launch; the model supports many.
`name` (translatable), `is_active`.

### User
A staff member who signs in. Extends Django's abstract user.
`email` (unique, the sign-in identifier), `full_name`, `role`, `department`, `branch`,
`language` (`ar` or `en`), `is_active`.

- `role` is a fixed choice of `AGENT` or `ADMINISTRATOR` (FR-022). Not user-configurable in the MVP.
- Deactivation must terminate existing sessions immediately (FR-026), so sessions are invalidated on
  the `is_active` transition rather than only at next sign-in.
- `language` satisfies FR-033.

## customers

### Organization
The customer. Scoped, soft-deletable.
`name`, `name_ar` (optional), `reference`, `notes` (reverse), `contacts` (reverse).

### Contact
A named person belonging to an organization. Scoped, soft-deletable.
`organization` (**nullable**), `full_name`, `preferred_language`, `is_unlinked` (derived from
`organization IS NULL`).

- A null `organization` is a legitimate state, not an error: the public form cannot determine an
  employer (FR-040). Such contacts are listed for staff attention (FR-041).
- Moving a contact between organizations is permitted and audited (FR-042). Tickets keep the
  organization they were raised under, so the ticket holds its own `organization` foreign key rather
  than reading through the contact.

### ContactDetail
A means of reaching a contact.
`contact`, `kind` (`EMAIL` or `PHONE`), `value`, `is_primary`.

- Email values are normalized to lower case before matching, so FR-002 contact matching is stable.
- Partial unique index on `(kind, value)` where not deleted, preventing duplicate contacts for one
  email address (SC-003).

### Note
Free text held against an organization. Scoped, soft-deletable.
`organization`, `author`, `body`.

## tickets

### Category
Administrator-maintained classification.
`name` (translatable), `is_active`.

### Ticket
One request for support. Scoped, soft-deletable.
`reference` (unique, `AZM-{year}-{sequence}`), `organization` (**nullable**, mirrors the contact's
organization at creation), `contact` (required), `subject`, `description`, `category`, `priority`,
`status`, `assigned_to` (nullable), `origin_channel`, `first_response_at`, `resolved_at`.

- `priority`: `LOW`, `NORMAL`, `HIGH`, `URGENT`, default `NORMAL` (assumption, pending confirmation).
- `origin_channel`: `WEB_FORM` or `EMAIL` in the MVP.
- `assigned_to` transitions from null to an agent when taken (FR-039). A transition from one agent
  to another is a reassignment requiring administrator permission (FR-008).
- Indexed on `(department, branch, status, priority, created_at)` to keep the queue responsive at
  the SC-009 volumes.

#### Status lifecycle

Assumption pending stakeholder confirmation. Transitions outside this set are rejected (FR-009).

```text
NEW ──────────▶ OPEN ──────────▶ PENDING_CUSTOMER
 │               │  ▲                   │
 │               │  └───────────────────┘
 │               ▼
 └──────────▶ RESOLVED ──────────▶ CLOSED
                 ▲                    │
                 └────────────────────┘   (reopen)
```

- `NEW` → `OPEN` on first agent action.
- `OPEN` ⇄ `PENDING_CUSTOMER` while awaiting a customer reply.
- Any active status → `RESOLVED` when the agent resolves.
- `RESOLVED` → `OPEN` automatically when a customer replies (spec edge case: a reply to a resolved
  ticket must not be lost).
- `RESOLVED` → `CLOSED` after a quiet period, or manually.
- `CLOSED` → `OPEN` on reopen.

### Message
One entry on a ticket thread.
`ticket`, `author` (nullable for inbound customer messages), `direction` (`INBOUND` or `OUTBOUND`),
`visibility` (`PUBLIC` or `INTERNAL`), `channel`, `body`, `delivery_status`, `delivery_error`,
`external_id`.

- `visibility` is the FR-014 and FR-015 boundary. **Every customer-facing serializer, template, and
  email filters on `visibility=PUBLIC`.** This is asserted by `tests/test_internal_visibility.py`
  rather than left to review.
- `delivery_status`: `PENDING`, `SENT`, `FAILED`. A failure is surfaced on the ticket (FR-016).
- `external_id` stores the provider message identifier used for inbound threading.

## messaging

### InboundMessageLog
Raw inbound mail as received, retained for diagnosis of threading failures.
`received_at`, `raw_headers`, `matched_ticket` (nullable), `match_method`, `processing_error`.

- `match_method` records which threading rule matched (reply-to token, headers, subject, or none),
  which makes FR-013 failures diagnosable instead of mysterious.

## Audit

### AuditEntry
Provided by `django-auditlog`, not hand-written.
`actor`, `timestamp` (UTC), `content_type`, `object_id`, `action`, `changes` (JSON diff of before and
after values).

- Immutable to all roles (FR-028): no update or delete path is exposed, and the administrative
  interface registers it read-only.
- Filterable by entity, actor, and date range (FR-029).
- Registered for: Organization, Contact, ContactDetail, Note, Ticket, Message, User, Department,
  Branch. `tests/test_audit_coverage.py` fails if a model inheriting `SoftDeleteModel` is not
  registered.

## Relationship summary

```text
Department ──┐
             ├──< Organization ──< Contact ──< ContactDetail
Branch ──────┘         │              │
                       │              └──< Ticket >── Category
                       └──< Note              │
                                              └──< Message
```

- A Contact may exist without an Organization (FR-040).
- A Ticket always has a Contact and keeps its own Organization reference (FR-042).
- A Message always belongs to a Ticket and carries its own visibility.

## Validation rules drawn from requirements

| Rule | Source |
|---|---|
| Intake requires name, email, subject, description; phone optional | FR-001 |
| Email addresses normalized and matched case-insensitively | FR-002, SC-003 |
| Ticket reference unique and immutable once assigned | FR-003 |
| Status transitions restricted to the lifecycle above | FR-009 |
| A ticket assigned to one agent cannot be taken by another without reassignment | FR-008 |
| Every message carries a visibility | FR-014 |
| Scoped models always carry a department and a branch | FR-023 |
| Deleted records remain recoverable | FR-020 |
| Arabic content stored and returned unchanged at every boundary | FR-035 |
