# Implementation Plan: The customer portal

**Branch**: `004-customer-portal` | **Date**: 2026-09-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/004-customer-portal/spec.md`

## Summary

Customers register, prove their email address, and then read, reply to and raise their own
support requests. Three product decisions were taken before the specification was written and
are requirements here, not options: email and password; full self-service; a customer sees the
tickets of their own confirmed address and nothing else.

**One research finding decides the shape of everything else.** The login middleware's rule is
*authenticated → let through*, and thirteen of roughly forty views carry a role check. A
customer stored as a `User` would therefore walk into the ticket queue, the customer list and
the chat console, and would see nothing only because they have no department. `role` also
defaults to `AGENT`, so such an account is one missing keyword argument from being staff.

So customers are a **separate account model with their own session**, and `request.user` goes
on meaning "a member of staff". Every existing staff screen then refuses a customer without
being modified, and the eleven places that assume `request.user.department` keep their
assumption safely. The cost is a second authentication flow, built rather than inherited. It is
the smaller cost: the alternative makes one forgotten guard a data breach.

The rest follows from that. Identity is a confirmed address matched to contacts at read time.
Replies and new requests go through the existing ticket services so they behave identically to
email. Internal messages stay out by joining the sweep that already exists, by directory rather
than by being listed.

## Technical Context

**Language/Version**: Python 3.10 (CI runs 3.12)

**Primary Dependencies**: Django 5.2 LTS, django-auditlog, django-ratelimit, htmx + Alpine.js.
**No new dependency.** Password hashing, session handling, rate limiting and email are all
already in use; what is new is the flow around them.

**Storage**: PostgreSQL in deployment and CI, SQLite locally. Two new tables; **no column
altered on any existing table**, which is a claim [data-model.md](data-model.md) asks a
reviewer to verify rather than trust.

**Testing**: pytest with pytest-django; Playwright for the browser checks, in its own session.

**Target Platform**: Linux, served over ASGI since ADR-007.

**Project Type**: Server-rendered web application (ADR-003). No SPA, no public interface for
other systems.

**Performance Goals**: Unchanged. The portal's list is one customer's tickets — the smallest
query in the product.

**Constraints**:
- A customer account MUST NOT reach a staff screen, and the refusal MUST rest on the account
  being a customer rather than on it having no scope (FR-028). This is the constraint the
  architecture is chosen for.
- Email delivery is a **precondition for release**, not a detail. Eight of twelve validation
  scenarios end in a message arriving, and `docs/email-setup.md` has not been actioned.

**Scale/Scope**: Six stories, 38 requirements, ten new routes, two new tables, one new
templates directory.

## Constitution Check

*GATE: passed before Phase 0, re-checked after Phase 1.*

### I. Test-First (NON-NEGOTIABLE) — PASS

Every story here is testable before it is built, and the refusals are the tests that matter.
FR-038 carries forward spec 003's addition: each check must be demonstrated to fail against the
defect it guards, because a check nobody has seen fail is a claim. Scenario 6 in
[quickstart.md](quickstart.md) is that requirement made concrete — force a department onto a
customer account and confirm the refusals still hold.

### II. Data Integrity & Auditability — PASS

Portal account creation, confirmation, sign-in failure, password change and customer-authored
content are all audited (FR-034). No existing column changes. Customer-authored content is
validated at the boundary before it reaches storage (FR-024), which is what the principle asks
of every mutation.

One point to carry into implementation: audit entries must not record a password or a link
value. The product has been here before — password hashes reached the audit log once and had to
be excluded, and the log is immutable, so anything that reaches it stays.

### III. Security & Access Control — PASS, and this is the principle the feature is about

Deny-by-default is the reason for the separate account model rather than a check applied on top
of a shared one. A customer is refused staff screens because `request.user` is not
authenticated for them — the existing middleware does the work, unmodified, for screens that do
not exist yet (FR-029).

Five new surfaces are introduced and each is named as a requirement rather than left implicit:
self-service registration, a password the customer chooses, a confirmation link, a reset flow,
and a lockout. Every one is rate-limited per address and per source; links are single-use and
expiring; responses do not reveal whether an address is known.

Secrets: passwords are stored irreversibly and link values are stored so the table is not a
list of live credentials — the same reasoning that governs the chat visitor token.

### IV. Simplicity & YAGNI — PASS, with the one deviation recorded below

No new dependency. No new abstraction over the ticket services — a portal reply goes through the
path an emailed reply goes through, because the alternative is two implementations of "a
customer replied" that diverge silently.

Deliberately excluded and recorded in the specification's Assumptions: an organization-wide
view, two-factor authentication, and any public interface for other systems. Each is a
reasonable next question and none is required by this feature.

**Re-check after Phase 1**: no new violations. The contracts add ten routes, five of which are
reachable without a session and each of which carries the written justification the existing
guard demands.

## Project Structure

### Documentation (this feature)

```text
specs/004-customer-portal/
├── plan.md              # This file
├── spec.md              # Six stories, 38 requirements
├── research.md          # Phase 0 — eight decisions
├── data-model.md        # Phase 1 — two new tables, nothing altered
├── quickstart.md        # Phase 1 — twelve validation scenarios
├── contracts/
│   └── http-endpoints.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 — created by /speckit-tasks
```

### Source code

One new application, because the portal is a separate audience with a separate identity and
putting it inside `accounts` would mix staff authentication with customer authentication in one
module — which is the mixing this design exists to avoid.

```text
apps/
├── portal/                   # new
│   ├── models.py             # CustomerAccount, CustomerToken
│   ├── auth.py               # sign in, sign out, the customer session
│   ├── middleware.py         # request.customer; refuses staff sessions
│   ├── services/
│   │   ├── registration.py   # register, confirm, the identical-response rule
│   │   ├── passwords.py      # reset, strength, lockout
│   │   └── tickets.py        # read and reply, through apps/tickets
│   ├── views.py
│   ├── urls.py
│   └── tests/
├── tickets/                  # unchanged; the portal calls its services
├── accounts/                 # unchanged; staff identity stays staff identity
└── core/
    └── middleware.py         # unchanged — it already refuses a customer

templates/portal/             # new, and entirely customer-facing
config/settings/base.py       # the portal's limits and link lifetimes
tests/test_internal_visibility.py   # templates/portal/ joins the sweep by directory
tests/test_anonymous_access.py      # five new exemptions, each justified
```

**Structure Decision**: a new application, and no change to `accounts` or `tickets` beyond
calling into them. `templates/portal/` is entirely customer-facing, so it joins the
internal-message sweep as a whole directory — unlike `templates/chat/`, which mixes both
audiences and must be classified template by template.

## Complexity Tracking

One deviation, recorded before the code is written as Constitution IV requires.

| Deviation | Why needed | Simpler alternative rejected because |
|---|---|---|
| A second account model and a second authentication flow, when Django provides one of each | The staff middleware admits anything authenticated and only thirteen views check a role, so a customer sharing `User` reaches the ticket queue and is saved only by having no department — the coincidence FR-028 exists to forbid. `role` also defaults to `AGENT`, making such an account one missing argument from staff | `Role.CUSTOMER` on `User` with the middleware tightened and every staff view guarded. Simpler to write and it makes one forgotten guard a breach, on a codebase where most views carry no guard today. It also cannot satisfy FR-029 — a staff screen added next year would need somebody to remember |

## Phase ordering note for `/speckit-tasks`

Stories 1, 2 and 6 are all P1 and are the smallest portal worth shipping: an account, a list,
and the guarantee that the account reaches nothing else.

Two ordering constraints are real rather than organisational:

1. **Story 6 is not last.** "A customer is not staff" is a property of the account model and
   the session, so it is built with them, not verified afterwards. Left to the end it becomes a
   sweep over work already done, and a sweep is what you do when you no longer trust the design.
2. **The internal-message sweep is extended before the first portal template exists.** Adding
   templates under a check that does not yet cover them is how a customer-facing screen ships
   unswept, and this project has already watched a catalog check report clean on a file it was
   not reading.
