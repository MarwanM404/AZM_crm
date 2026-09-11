# ADR-001: Django as the web framework

**Status**: Accepted
**Date**: 2026-09-11
**Roadmap decision**: #1
**Relates to**: [spec 001-mvp-ticket-desk](../../specs/001-mvp-ticket-desk/spec.md)

## Context

The MVP specification requires, on day one: bilingual Arabic and English interfaces with correct
right-to-left layout (FR-031 to FR-036), deny-by-default authorization on every action (FR-021),
an immutable audit trail capturing before and after values for every write (FR-027 to FR-030),
soft deletion with recovery (FR-020), and administrator management of users and categories
(FR-025). The constitution additionally requires reversible, version-controlled migrations and a
Python backend.

These are not evenly distributed across Python web frameworks. Bilingual-at-launch, decided on
2026-09-11, makes internationalization support a primary selection criterion rather than a
secondary convenience.

## Decision

Use Django as the web framework.

## Consequences

**Gained**

- Internationalization is a first-class framework feature: `gettext` catalogs, locale middleware,
  per-user language persistence, pluralization, and locale-aware date and number formatting. This
  covers FR-031 through FR-035 with framework code rather than project code.
- Authentication, permissions, and groups ship with the framework, giving FR-021 through FR-026 a
  foundation instead of a from-scratch build. Session-based authentication satisfies FR-026
  (immediate termination on deactivation) without the token revocation machinery a stateless scheme
  would need.
- The ORM provides reversible migrations, satisfying a constitutional requirement directly.
- `django-admin` provides user, department, branch, and category management without bespoke
  screens, which is meaningful MVP time saved on FR-025.
- The audit requirement has mature off-the-shelf options (`django-auditlog`, `django-simple-history`)
  that record actor and before/after values. Evaluate both during planning; do not hand-roll.

**Accepted costs**

- Django's conventions are opinionated. Fighting them is expensive, so the project follows them.
- The framework is larger than an API-only alternative. Under constitution Principle IV this is
  justified by the number of requirements it satisfies directly rather than by preference.
- Asynchronous work is not the framework's natural mode. Live chat, arriving immediately after the
  MVP, needs Django Channels. See ADR-005.

## Alternatives considered

- **FastAPI**: lighter and API-first, but internationalization, admin, authentication, permissions,
  and migrations would each be assembled from separate libraries or written. With bilingual launch
  locked, that assembly work lands directly on the critical path.
- **Flask**: same objection as FastAPI, with a smaller asynchronous story.
