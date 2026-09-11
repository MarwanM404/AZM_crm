# ADR-004: Explicit department and branch scoping

**Status**: Proposed
**Date**: 2026-09-11
**Roadmap decision**: #4
**Relates to**: [spec FR-023, FR-024, FR-038](../../specs/001-mvp-ticket-desk/spec.md)

## Context

FR-023 requires every data query to be scoped by the acting user's department and branch. FR-024
requires that records outside that scope are not merely hidden but undisclosed. FR-038 sets agent
visibility at department-wide.

The organization runs a single branch at launch, but the roadmap requires the data model to support
several so that multi-branch operation later needs no migration. This is the cheap-now, expensive-
later case the roadmap is built around: a scope column costs little in the first model and a great
deal once forty tables exist.

## Decision

Scope by columns on the records themselves, not by separate databases or schemas.

- Every scoped model carries `department` and `branch` foreign keys, set at creation and never
  inferred at read time.
- Scoped models expose an explicit `for_user(user)` queryset method that applies the scope filter.
  Views call it. There is no implicit, thread-local, globally applied filter.
- A test asserts that every model inheriting the scoped base exposes `for_user` and that its
  unfiltered manager is not reachable from view code.
- Tickets additionally retain the organization they were raised under (FR-042), independently of the
  contact's current organization.

## Consequences

**Gained**

- One database, one migration path, one backup. Cross-department reporting in a later phase is a
  query, not a federation problem.
- Explicitness. A reader of a view can see whether scoping was applied. Implicit global filters read
  well in demos and fail quietly when a code path bypasses the manager, which is precisely the
  FR-024 failure mode.
- Multi-branch operation requires no data migration when the organization grows.

**Accepted costs**

- Every view must remember to call `for_user`. The mitigation is the test above plus a review gate,
  not trust.
- Scope columns appear on most tables. This is intentional redundancy in exchange for query
  simplicity.
- A misassigned scope value is a data problem rather than an access-control bug, so the
  administrator screens that set department and branch need care.

## Alternatives considered

- **Implicit filtering through a thread-local current user**: less code at each call site, but scope
  becomes invisible at the point of use and untestable in isolation. Rejected on FR-024 risk.
- **Schema or database per branch**: strong isolation, disproportionate operational cost for one
  branch, and painful for the cross-branch reporting phase 9 will require.

## Open

This record is `Proposed` pending one business answer the roadmap already flagged: **do branches
ever legitimately share data?** If an agent in one branch must be able to work a ticket belonging to
another, the rule above needs an explicit, audited exception rather than a workaround.
