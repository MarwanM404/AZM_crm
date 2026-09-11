# Contract: HTTP endpoints

**Date**: 2026-09-11 | **Plan**: [../plan.md](../plan.md)

The application is server-rendered, so the contract is the set of URLs, who may reach them, and what
they return. Each row is a contract test.

**Access column**: `public` = no authentication; `agent` = any signed-in staff member within scope;
`admin` = Administrator role only.

**Scope rule**: every row marked scoped applies `for_user(request.user)`. A request for a record
outside the acting user's department and branch returns **404, not 403** — a 403 would confirm the
record exists and violate FR-024.

## Public

| Method | Path | Access | Returns | Requirement |
|---|---|---|---|---|
| GET | `/request/` | public | Intake form in the visitor's language | FR-001, FR-031 |
| POST | `/request/` | public | 302 to confirmation with reference, or 200 with field errors | FR-001, FR-002, FR-005, FR-006 |
| GET | `/request/submitted/<reference>/` | public | Confirmation showing the reference only, no customer data | FR-004 |

The confirmation page must not disclose any stored customer information beyond the reference the
visitor just created.

## Authentication

| Method | Path | Access | Returns | Requirement |
|---|---|---|---|---|
| GET, POST | `/sign-in/` | public | Sign-in form; 302 to queue on success | FR-021 |
| POST | `/sign-out/` | agent | 302 to sign-in | — |
| POST | `/language/` | agent | 204 and persisted language choice | FR-033 |

Every other path requires authentication by middleware default (FR-021). A deactivated account is
refused on the next request, not at next sign-in (FR-026).

## Tickets

| Method | Path | Access | Returns | Requirement |
|---|---|---|---|---|
| GET | `/tickets/` | agent, scoped | Queue of all department tickets, paginated, sorted by priority then age | FR-011, FR-038 |
| GET | `/tickets/?assigned=me&status=&priority=&category=&q=` | agent, scoped | Same list filtered; htmx returns the list fragment only | FR-011 |
| GET | `/tickets/<reference>/` | agent, scoped | Ticket detail with thread, customer context, and history | FR-007, FR-010 |
| POST | `/tickets/<reference>/take/` | agent, scoped | Assigns to caller; **409** if already assigned | FR-008, FR-039 |
| POST | `/tickets/<reference>/assign/` | admin, scoped | Assigns or reassigns to a named agent | FR-008, FR-039 |
| POST | `/tickets/<reference>/status/` | agent, scoped | Applies a transition; **422** if outside the lifecycle | FR-009 |
| POST | `/tickets/<reference>/fields/` | agent, scoped | Updates category or priority, records before and after | FR-010 |
| POST | `/tickets/<reference>/reply/` | agent, scoped | Queues an outbound public message, returns the appended thread fragment | FR-012 |
| POST | `/tickets/<reference>/note/` | agent, scoped | Appends an internal message, never customer-visible | FR-014, FR-015 |

The 409 on `take` is the contract for the concurrent-take edge case: exactly one agent succeeds.

## Customers

| Method | Path | Access | Returns | Requirement |
|---|---|---|---|---|
| GET | `/customers/` | agent, scoped | Organization list, paginated | FR-017 |
| GET | `/customers/<id>/` | agent, scoped | Organization with contacts and combined timeline | FR-019 |
| GET | `/customers/<id>/timeline/?contact=<id>` | agent, scoped | Timeline narrowed to one contact | FR-019 |
| POST | `/customers/<id>/note/` | agent, scoped | Appends an attributed note | FR-018 |
| GET, POST | `/customers/<id>/edit/` | agent, scoped | Updates organization details | FR-017 |
| GET | `/contacts/unlinked/` | agent, scoped | Contacts awaiting an organization | FR-041 |
| POST | `/contacts/<id>/link/` | agent, scoped | Links a contact to an existing or new organization | FR-041, FR-042 |
| GET, POST | `/contacts/<id>/edit/` | agent, scoped | Updates contact and contact details | FR-017 |
| POST | `/customers/<id>/delete/` | admin, scoped | Soft-deletes, recoverable, audited | FR-020 |

## Administration

| Method | Path | Access | Returns | Requirement |
|---|---|---|---|---|
| GET, POST | `/admin/users/` | admin | Create and list staff accounts | FR-025 |
| POST | `/admin/users/<id>/deactivate/` | admin | Deactivates and terminates sessions | FR-026 |
| GET | `/admin/audit/?entity=&actor=&from=&to=` | admin | Filtered audit log, read-only | FR-029 |
| GET, POST | `/admin/categories/` | admin | Category management | FR-007 |

No endpoint permits editing or deleting an audit entry (FR-028).

## Cross-cutting response rules

1. Out-of-scope record: **404**, never 403 (FR-024).
2. Unauthenticated request to a non-public path: **302** to sign-in (FR-021).
3. Authenticated but insufficient role: **403**, and the attempt is recorded (FR-021, spec US4-2).
4. Every mutating request is CSRF-protected and returns the updated fragment for htmx callers.
5. Every response carries `lang` and `dir` matching the active language (FR-032).
6. No response includes a message with `visibility=INTERNAL` on a customer-facing path (FR-015).
