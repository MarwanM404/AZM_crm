# Phase 0 Research: MVP Ticket Desk

**Date**: 2026-09-11 | **Plan**: [plan.md](plan.md) | **Spec**: [spec.md](spec.md)

Each item resolves an unknown from the plan's Technical Context or a requirement whose
implementation approach was not obvious.

## 1. Audit trail implementation

**Decision**: `django-auditlog`, registered on every customer-facing model, with the acting user
supplied by middleware for web requests and passed explicitly by Celery tasks.

**Rationale**: FR-027 requires actor, UTC timestamp, entity, action, and the before and after values
of changed fields. `django-auditlog` stores exactly this as a JSON diff in a single table, which
suits PostgreSQL `JSONB` and keeps the audit query in FR-029 to one table. Registration is
declarative, so adding a model to the audit scope is one line rather than a new code path, which is
what makes the cross-cutting `test_audit_coverage.py` check meaningful.

**Alternatives considered**: `django-simple-history` creates a shadow table per model, giving richer
point-in-time reconstruction at the cost of doubling the schema and complicating FR-029's single
filterable log. A hand-rolled audit layer was rejected under constitution Principle IV.

**Consequence**: Celery tasks have no request and therefore no implicit actor. Any task writing to a
customer record must set the actor explicitly, or the trail will attribute human work to a system
user. This is a review gate, not a convention.

## 2. Deny-by-default authorization

**Decision**: Django's `LoginRequiredMiddleware` applied globally, with the public intake form and
the sign-in views as the only exemptions, marked explicitly. Object-level scope is enforced by
`ScopedQuerySet.for_user(user)`, called in every view that reads scoped data.

**Rationale**: FR-021 requires that absence of a check is a failure rather than a permissive
default. Middleware inverts the default for authentication; the explicit queryset call keeps scope
visible at the point of use. FR-024 additionally requires that out-of-scope records are not
disclosed, which means a scope miss must produce the same response as a missing record — a 404, not
a 403, since a 403 confirms existence.

**Alternatives considered**: Per-view decorators alone were rejected because a forgotten decorator
fails open. An implicit thread-local scope filter was rejected in ADR-004 because scope becomes
invisible at the call site and untestable in isolation.

**Consequence**: `tests/test_scope_isolation.py` asserts, for every scoped model, that a user outside
the scope receives a not-found response rather than a forbidden one.

## 3. Inbound email threading

**Decision**: Accept inbound mail through a provider webhook where the chosen provider offers one,
falling back to IMAP polling on a Celery Beat schedule. Both feed one ingestion function behind an
adapter. Thread by, in order: a reply-to address carrying the ticket reference
(`support+REF@domain`), then the `In-Reply-To` and `References` headers, then the reference token in
the subject line. If none match, create a new ticket.

**Rationale**: FR-013 requires replies to attach to the originating ticket and unmatched mail to
create a new ticket. Plus-addressing is the most reliable signal because it survives clients that
rewrite subjects and strip headers. Header matching covers clients that preserve threading but
rewrite the recipient. Subject matching is the last resort because customers edit subjects.

**Alternatives considered**: Subject-line matching alone is the traditional approach and is
unreliable in both directions — it misses edited subjects and wrongly merges unrelated tickets that
quote a reference. Running a dedicated SMTP listener was rejected as operational surface the MVP
does not need.

**Consequence**: The outbound reply-to address must be configurable and must be a real deliverable
address. This is a deployment dependency, noted below.

## 4. Ticket reference format

**Decision**: `AZM-{year}-{sequence}`, with the sequence zero-padded to six digits and allocated per
year from a database sequence. Example: `AZM-2026-000123`.

**Rationale**: FR-003 requires a unique, stable, human-quotable reference. Customers read these
aloud on the phone, so the format avoids ambiguous characters and stays short.

**Alternatives considered**: A random opaque token would prevent volume inference from a reference,
but FR-024 is satisfied by authorization rather than by unguessable identifiers, and an opaque token
is hostile to read over the phone. UUIDs were rejected for the same reason.

**Consequence**: The reference discloses approximate ticket volume to anyone holding one. This is
accepted; it is not a substitute for the access control that actually protects the records.

## 5. Bilingual interface and right-to-left layout

**Decision**: Django `gettext` with `LocaleMiddleware`, the active language persisted on the user
profile and in the session, `dir` and `lang` attributes set on the `html` element from
`get_language_bidi`, CSS using logical properties throughout, and separate email templates per
language selected by the recipient's recorded language.

**Rationale**: FR-031 to FR-035 cover screens and email in one requirement group, and ADR-003 keeps
them in one catalog. Arabic pluralization has six forms, which `gettext` handles and ad-hoc string
formatting does not.

**Alternatives considered**: Machine translation at render time was rejected for quality and cost.
Duplicated templates per language were rejected as an immediate maintenance failure.

**Consequence**: `tests/test_i18n_completeness.py` fails the build when a template introduces a
string outside a translation tag, and Playwright checks that the rendered `dir` attribute and
layout are correct on each MVP screen. This is how SC-007 becomes verifiable rather than a review
opinion.

## 6. Public form abuse protection

**Decision**: `django-ratelimit` backed by Redis, keyed on client address and on submitted email
address, combined with a hidden honeypot field and a minimum form-completion time check.

**Rationale**: FR-006 requires limiting abusive volume without blocking legitimate customers. Redis
gives a counter shared across worker processes, which a per-process counter cannot.

**Alternatives considered**: A CAPTCHA was rejected: it degrades accessibility, penalizes the
legitimate customer, and is not required at the MVP's expected volume.

**Consequence**: Redis is on the critical path for public intake. If it is unavailable, the system
must fail open on rate limiting rather than reject genuine customers, while logging the degradation.

## 7. Soft deletion

**Decision**: A `SoftDeleteModel` base carrying `deleted_at` and `deleted_by`, with the default
manager excluding deleted rows and an explicit `all_objects` manager for administrative recovery.

**Rationale**: FR-020 requires soft deletion by default and recoverability. Making the default
manager safe means a forgotten filter hides data rather than exposing it.

**Consequence**: Unique constraints must account for soft-deleted rows, or a deleted record blocks
reuse of its email address. Partial unique indexes conditioned on `deleted_at IS NULL` resolve this,
and PostgreSQL supports them directly.

## 8. Scale assumptions

**Decision**: Design for 50 concurrent agents, 3 departments, 50,000 tickets, and 10,000 customer
organizations.

**Rationale**: SC-009 states the data volumes. SC-010 states "the organization's full agent
population" without a number, so 50 is assumed as a working figure that comfortably exceeds a
typical support team and keeps the design honest about pagination and indexing.

**Consequence**: Queue and timeline views are paginated and indexed on their filter columns from the
first implementation. Confirm the real agent count with stakeholders; an order-of-magnitude
difference would change caching decisions but not the data model.

## Open deployment dependency

Two items cannot be resolved by research and are carried as risks, both waiting on
[ADR-006](../../docs/decisions/006-deployment-target.md):

1. **Encryption of personal data at rest.** Constitution Principle III requires it. The mechanism is
   a property of the host — encrypted volumes, a managed database with encryption enabled, or
   filesystem-level encryption. It blocks production release, not Phase 1 design.
2. **Persistent worker processes and Redis availability.** ADR-005 assumes both. Constrained hosting
   that cannot run them would force a rethink of background work before implementation starts.

A third, smaller dependency: the outbound reply-to address and inbound mail route from item 3 must
exist before the intake and reply flows can be tested end to end against a real mailbox.
