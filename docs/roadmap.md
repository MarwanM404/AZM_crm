# AZM Customer Support CRM — Roadmap

**Status**: draft
**Last updated**: 2026-09-11
**Source of requirements**: [`docs/requirements/azm_squad_customer_support_crm.pdf`](requirements/azm_squad_customer_support_crm.pdf)
**Governed by**: [`.specify/memory/constitution.md`](../.specify/memory/constitution.md) v1.0.0

## Purpose

This document sequences the twelve feature areas in the requirements PDF into delivery
phases, explains why that order was chosen, and records the decisions that must be made
before implementation starts. It is a planning artifact, not a specification. Each phase
below becomes one or more Spec Kit features via `/speckit-specify`.

## How the order was derived

The PDF lists features by business prominence. This roadmap re-sorts them by technical
dependency and by the constraints the constitution already imposes:

1. **Audit and authorization come first.** Constitution Principle II requires an audit
   entry for every customer-record mutation, and Principle III requires an explicit
   authorization check on every endpoint. Both are cheap to build into the first model
   and expensive to retrofit across a finished schema.
2. **Cross-cutting platform choices come first.** Bilingual Arabic/English with RTL
   layout, multi-department and multi-branch data scoping, and per-tenant branding
   (PDF section 12) affect every table, every query, and every template. They are
   decided in Phase 0 and enforced from Phase 1, never bolted on.
3. **Data before insight.** Reports (section 9) and AI features (section 7) consume
   ticket and knowledge-base data. They cannot be validated before that data exists,
   so they are sequenced after the systems that produce it.
4. **One channel, then many.** Channel integrations (section 3) share an inbound and
   outbound message abstraction. The abstraction is proven on email first, then reused;
   building five channels in parallel produces five incompatible shapes.

## Phase plan

Each phase lists the PDF section it satisfies, its deliverable, and the exit criterion
that must hold before the next phase starts.

### Phase 0 — Foundations and decisions
*PDF: 12 (partial)*

Project skeleton, dependency management, formatter/linter/type-checker configuration,
test harness, CI pipeline, local development setup, and the architecture decision records
for every item under "Open decisions" below. Database chosen and connected, migration
tooling wired.

**Exit criterion**: `pytest` runs green on an empty suite in CI, quality gates from the
constitution are enforced automatically, and no open decision below is still open.

### Phase 1 — Identity, roles, permissions, audit
*PDF: 10*

Users, authentication, role definitions, permission enforcement helper, audit-log model
and the write path that records actor, timestamp, entity, action, and changed-field
before/after values. Department and branch scoping primitives that later models inherit.

**Exit criterion**: an unauthorized request to any endpoint is denied by default, and
every write in the system produces a queryable audit entry.

### Phase 2 — Customer management
*PDF: 1*

Customer profiles, contact details, notes, file attachments, and the interaction-history
timeline that later phases append to.

**Exit criterion**: a customer record can be created, edited, soft-deleted, and its full
change history reconstructed from the audit log.

### Phase 3 — Ticket core
*PDF: 2*

Tickets linked to customers, categories, priorities, status lifecycle, assignment to
agents, escalation state, and ticket history.

**Exit criterion**: a ticket moves through its full lifecycle, and every transition is
recorded with actor and timestamp.

### Phase 4 — Agent dashboard and collaboration
*PDF: 4*

Assigned-ticket queue, customer context panel, tasks and reminders, quick replies, and
internal notes or mentions for team collaboration.

**Exit criterion**: an agent can work a ticket end to end without leaving the dashboard.

### Phase 5 — Communication channels
*PDF: 3*

Shared inbound/outbound message abstraction, delivered in order: email, web forms,
**live chat**, WhatsApp, SMS. Each channel maps messages onto the ticket thread.

Live chat is sequenced ahead of WhatsApp and SMS by decision on 2026-09-11, and carries
more than a channel adapter:

- A customer and an agent converse in real time; the transcript persists onto the ticket.
- An administrator or supervisor can observe an in-progress conversation together with the
  customer's profile and ticket context.
- That observer can send a **private note to the agent** during the conversation. Private
  notes are never visible to the customer under any circumstance.

Because chat is synchronous, it additionally requires persistent connections, agent
presence and capacity state, a waiting queue for when no agent is free, session timeout
handling, and transcript-to-ticket mapping. Budget it as the largest of the five channels.

**Exit criterion**: a reply sent from any live channel appears on the ticket thread, an
inbound message on any live channel creates or updates a ticket, and an automated test
proves that no message marked internal can appear in a customer-facing payload.

### Phase 6 — SLA and automation
*PDF: 5*

Response and resolution targets per category or priority, automatic assignment rules,
escalation rules, and the alert and notification delivery path.

**Exit criterion**: a ticket that breaches its target escalates and notifies without
manual intervention.

### Phase 7 — Knowledge base
*PDF: 6*

FAQs, help articles, solution guides, and search. Bilingual content from the start.

**Exit criterion**: an agent can find and attach a published article to a ticket reply.

### Phase 8 — Customer portal
*PDF: 8*

Customer-facing ticket submission, request tracking, history, FAQ access, and
satisfaction feedback. Reuses Phase 1 authorization with a customer-scoped role.

**Exit criterion**: a customer sees only their own records, verified by test.

### Phase 9 — Reports and management dashboards
*PDF: 9*

Ticket reports, SLA performance, agent performance, customer satisfaction, and
management dashboards.

**Exit criterion**: each report is reproducible from raw data and matches a
hand-calculated figure in test.

### Phase 10 — AI features
*PDF: 7*

Ticket summaries, suggested replies, automatic categorization, suggested solutions drawn
from the knowledge base, and the customer-facing chatbot. Every AI output is a suggestion
surfaced to a human, never an unattended write to a customer record.

**Exit criterion**: AI suggestions are measurably better than the no-AI baseline on a
held-out set of real tickets, and every suggestion is attributable and reversible.

### Phase 11 — External integrations
*PDF: 11*

Public API surface, ERP integration, and the external-system connectors beyond the
messaging providers already delivered in Phase 5.

**Exit criterion**: the public API is versioned, documented, and contract-tested.

### Cross-cutting, enforced from Phase 1 onward
*PDF: 12*

Arabic and English throughout with correct RTL layout, responsive web and mobile
presentation, multi-department and multi-branch scoping on every scoped query, and
configurable branding. These are review gates on every phase, not a phase of their own.

## Open decisions

These block Phase 0 exit. Each becomes a short architecture decision record in
`docs/decisions/`.

| # | Decision | Notes |
|---|----------|-------|
| 1 | Web framework | Django (batteries, admin, i18n, auth) vs FastAPI (lighter, API-first) |
| 2 | Database engine | Constitution requires relational with enforced foreign keys |
| 3 | Frontend approach | Server-rendered templates vs separate SPA against the API |
| 4 | Tenancy model | How department and branch scope rows, and whether branches ever share data |
| 5 | Background jobs | Required by SLA timers, escalation, and channel polling |
| 6 | WhatsApp and SMS providers | Determines Phase 5 cost, effort, and approval lead time |
| 7 | AI provider and data policy | What customer data may leave the system, and under what contract |
| 8 | Deployment target | Drives configuration, secret management, and CI delivery |

## Unknowns to confirm with stakeholders

The requirements PDF is a feature list. Before Phase 2, confirm: the concrete role list
and what each role may see; actual SLA target values per priority; expected ticket volume
and number of agents; data-retention and erasure obligations; which ERP system is in
scope; and whether any existing customer or ticket data must be migrated in.

## Working method

Each phase runs the Spec Kit loop: `/speckit-specify` to write the specification,
`/speckit-clarify` to close gaps, `/speckit-plan` for design, `/speckit-tasks` to break it
down, then `/speckit-implement`. No code is written for a phase that has no approved
specification.

## Release scope — Phase One MVP

### The cut line

**Phase One MVP is a vertical slice, not the first N phases.** It takes the thinnest
path through Phases 0–5 that still lets a real agent resolve a real customer ticket
end to end, and stops there.

The MVP is complete when this single flow works in production:

> A customer submits a request through a web form. A ticket is created and linked to a
> customer record. An agent sees it in their queue, takes it, replies by email, and
> resolves it. Every step is recorded in the audit log, and the customer's full history
> is reconstructable.

Nothing that does not serve that sentence is in the MVP.

### In scope

| # | Work item | Drawn from | Thinned to |
|---|-----------|------------|------------|
| M1 | Project skeleton, CI, quality gates, migrations | Phase 0 | Full — no thinning, this is the floor |
| M2 | Architecture decisions 1–5 | Phase 0 | Providers (6) and AI policy (7) deferred |
| M3 | Auth, two roles (agent, admin), permission check, audit log | Phase 1 | Two roles only, no custom role builder |
| M4 | Department and branch columns + scoped query base | Phase 1 | Columns and scoping enforced; no management UI |
| M5 | Customer profile, contacts, notes, interaction timeline | Phase 2 | Attachments deferred if they slip |
| M6 | Ticket: create, categorize, prioritize, assign, status lifecycle, history | Phase 3 | Fixed status set, no escalation state machine |
| M7 | Agent queue and ticket detail view | Phase 4 | Queue + detail only; no tasks, reminders, quick replies |
| M8 | Web form intake and outbound email reply on the shared message abstraction | Phase 5 | Two channels of five; abstraction built for the other three |
| M8a | Message `visibility` field (public / internal) + customer-payload exclusion test | Phase 4/5 | One field, one serializer rule, one test. Pulled forward for live chat |
| M9 | Arabic and English on every MVP screen, RTL-correct layout, i18n scaffolding | Cross-cutting | Only MVP screens translated, not future ones. Both locales are **not** thinnable |

### Explicitly deferred

Out of the MVP, in roughly the order they should follow it:

- **SLA and automation** (Phase 6) — target values are business data you do not have yet.
  Ship first, observe real response times for a few weeks, then encode targets you
  measured instead of targets you guessed.
- **Live chat** (Phase 5) — the first feature built after the MVP ships. Deferred out of
  the MVP because synchronous messaging roughly doubles the channel work, but promoted
  ahead of WhatsApp and SMS because it is the channel that matters most to the business.
  M8a puts its private-note foundation in place during the MVP.
- **WhatsApp and SMS** (rest of Phase 5) — after live chat. Each carries provider approval
  lead time and cost. M8 builds the abstraction they plug into, so adding them is additive.
- **Knowledge base** (Phase 7), **customer portal** (Phase 8), **reports** (Phase 9) —
  each is valuable and each is independent of the core loop.
- **AI features** (Phase 10) — depend on a ticket corpus and a knowledge base that do not
  exist at MVP time. Building them earlier means evaluating them on synthetic data.
- **ERP and external integrations** (Phase 11) — require a stable public API, which
  should stabilize against real internal usage first.
- **Attachments, tasks, reminders, quick replies, custom branding, agent-configurable
  roles** — all real requirements, none of them load-bearing for the flow above.

### Why this line and not another

Earlier than M8 is not a product: a ticket system with no intake and no reply channel
cannot be used by anyone outside the team, so it generates no real data and no real
feedback. Later than M8 delays that same feedback while the most assumption-heavy
features — SLA targets, AI quality, report definitions — get built against guesses. This
line is the first point where the system does a complete job for a real user, and every
deferred item is additive rather than structural.

### Decisions on the MVP scope

**1. Bilingual at launch — DECIDED 2026-09-11.** Arabic and English both ship in the MVP,
with correct RTL layout on every MVP screen. English-first is rejected. Consequences that
now bind earlier phases:

- Every MVP screen is reviewed in both locales before it is considered done. A screen that
  works only in LTR is incomplete, not "pending translation".
- CSS uses logical properties (`inline-start` / `inline-end`) rather than `left` / `right`.
  This convention is set in Phase 0 and enforced in review from the first screen.
- User-facing strings are externalized from the first commit. No hardcoded display text.
- Locale-aware formatting for dates, numbers, and names is a Phase 0 utility, not a
  per-screen concern.
- Decision #1 in "Open decisions" (web framework) is now weighted toward a framework with
  mature built-in i18n, locale middleware, and pluralization support.
- Seed and test data include Arabic content, so RTL and encoding problems surface in the
  test suite rather than in production.

**2. Contractual obligations — OPEN.** If a client agreement names the customer portal,
specific reports, or any other deferred item in the first delivery milestone, that item
moves into the MVP regardless of the sequencing argument above. Confirm before Phase 0
exits; absorbing it now is cheap, absorbing it mid-build is not.

