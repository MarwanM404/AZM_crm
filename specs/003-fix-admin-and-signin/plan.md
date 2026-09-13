# Implementation Plan: Administration visibility, bilingual correctness, and the sign-in screen

**Branch**: `003-fix-admin-and-signin` | **Date**: 2026-09-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/003-fix-admin-and-signin/spec.md`

## Summary

Five defects reproduced on 2026-09-13, plus a sign-in screen that does not look like the product
and cannot be used to test the three staff roles.

Two of the defects share a shape, and that shape decides the approach. **The system succeeded
and said nothing.** An account was created in a department its creator cannot see; a translation
was present, complete, unflagged, and wrong. Neither is an error, which is why 719 passing tests
and a clean catalog report both missed them.

So the work is in three layers rather than five fixes:

1. **Close the instances** — the scope default, the scopeless administrator, the wrong
   translation, the missing client-side catalog, the audit log, the sign-in screen.
2. **Close the classes** — an action whose result the acting user cannot see must say so
   (FR-020); a check that can only detect absence must not report correctness (FR-021).
3. **Prove the checks** — every check added here is demonstrated to fail when its defect is
   reintroduced deliberately, because a check nobody has seen fail is a claim.

Nothing stored changes. No dependency is added. The one new capability — quick sign-in — is
designed around its failure mode rather than its feature, because it is the only thing here that
can do harm.

## Technical Context

**Language/Version**: Python 3.10 (3.12 unavailable on this machine; CI runs 3.12)

**Primary Dependencies**: Django 5.2 LTS, django-auditlog, htmx + Alpine.js. **No new
dependency** — every decision in [research.md](research.md) uses what is already here, which is
the answer Constitution IV asks for.

**Storage**: PostgreSQL in deployment and CI, SQLite for the local suite. No schema change.

**Testing**: pytest with pytest-django; Playwright for the browser checks, in its own session.

**Target Platform**: Linux, served over ASGI since ADR-007.

**Project Type**: Server-rendered web application (ADR-003). No SPA.

**Performance Goals**: Unchanged. One screen gets faster — the audit log stops rendering sixteen
rows of detail per entry.

**Constraints**: Quick sign-in MUST be unreachable in production by every route, including a
direct request with no control rendered. This is the only hard constraint the feature adds, and
it is the reason the feature is acceptable at all.

**Scale/Scope**: Six user stories, 25 functional requirements, seven screens touched. No new
models, no migration except a constraint decision recorded as deliberately *not* taken.

## Constitution Check

*GATE: passed before Phase 0, re-checked after Phase 1.*

### I. Test-First (NON-NEGOTIABLE) — PASS, and this is the principle the feature is about

The constitution already requires that every bug fix begin with a regression test reproducing
the defect. This feature goes one step further because of what it found: FR-021 requires every
*check* to be demonstrated failing, not merely every fix to be preceded by a failing test.

The distinction earned its place. The catalog checks were written test-first, pass, and have
always passed — while a heading displayed a raw placeholder. They were never seen to fail
against a wrong translation because nobody wrote a wrong translation to try. Test-first
guarantees the test can fail for *some* reason; it does not guarantee it can fail for *the*
reason.

### II. Data Integrity & Auditability — PASS

Nothing stored is altered. Audit entries are immutable (MVP FR-028) and this work is display
only. No migration is added; [data-model.md](data-model.md) records why making the scope fields
non-null was considered and rejected rather than simply not done.

### III. Security & Access Control — PASS, with the feature's one risk made explicit

Deny-by-default is the design of the quick sign-in gate, not a check applied to it afterwards:
off by default, forced off in production configuration rather than read from the environment
there, refused at the route as well as hidden in the interface.

Two smaller points in the same principle:

- A scopeless account is **not** treated as seeing everything. That reading is the one
  escalation this defect could have produced, and research.md rejects it explicitly.
- The self-service scope change (FR-005) is a deliberate narrowing of an existing rule, allowed
  only from *no* scope and never between scopes. It is recorded in Complexity Tracking below
  rather than left to be discovered in review.

No secret is added. The demonstration passwords quick sign-in uses are already in this
repository, which is what makes it safe to have and worthless to steal.

### IV. Simplicity & YAGNI — PASS

No new dependency. No new model. No configuration switch beyond the single one the security
requirement forces, and that one has exactly one legitimate value in a real deployment.

The translation check is one rule — a translation may not add a placeholder its source lacks —
chosen because it was measured to catch the real defect with no false positives, not because it
was the most thorough rule available. Larger schemes were considered and rejected in research.md.

**Re-check after Phase 1**: no new violations. Contracts add three routes, two of which are
framework wiring that should already have existed.

## Project Structure

### Documentation (this feature)

```text
specs/003-fix-admin-and-signin/
├── plan.md              # This file
├── spec.md              # Six stories, 25 requirements
├── research.md          # Phase 0 — eight decisions
├── data-model.md        # Phase 1 — what does NOT change, and why
├── quickstart.md        # Phase 1 — nine validation scenarios
├── contracts/
│   └── http-endpoints.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 — created by /speckit-tasks
```

### Source code

Existing layout. No new application; every change lands in code that already exists.

```text
apps/
├── accounts/
│   ├── views_admin.py        # scope defaulting and refusal (US1)
│   ├── views.py              # sign-in, anonymous language choice (US4, US5)
│   ├── models.py             # bilingual name property (US3)
│   └── management/commands/  # first-administrator bootstrap (US2)
├── core/
│   ├── views.py              # audit log rendering (US6)
│   └── templatetags/         # audit field naming (US6)
└── chat/                     # untouched; it is where the symptom showed, not the cause

config/
├── urls.py                   # client-side catalog route (US3)
└── settings/
    ├── base.py               # quick sign-in flag, off (US5)
    └── production.py         # forced off (US5)

templates/
├── accounts/
│   ├── sign_in.html          # the shell, language switch, quick sign-in (US4, US5)
│   └── users.html            # scopeless explanation, created-account confirmation (US1, US2)
└── core/audit_log.html       # readable entries (US6)

static/js/                    # no change — gettextOrFallback already correct
tools/catalog.py              # placeholder-mismatch rule (US3)
tests/                        # the sweeps, and the demonstrations that each check fails
```

**Structure Decision**: no structural change. This is a defect feature, and every file above
already exists except the bootstrap command. A defect feature that grows the project's shape is
usually fixing the wrong thing.

## Complexity Tracking

Two deviations, both recorded before the code is written as Constitution IV requires.

| Deviation | Why needed | Simpler alternative rejected because |
|---|---|---|
| An administrator may set their own scope, but only when they have none (FR-005) | Everywhere else, scope is administered by someone else. With one administrator and no scope — the state a new installation starts in — that rule makes the product unrecoverable from its own first screen | Requiring a second, already-scoped administrator assumes one exists. On a new installation none does, and the first account is exactly the broken one |
| A configuration switch, when Constitution IV calls unused switches a defect (quick sign-in) | The switch is not the feature, it is the containment. Its off state is the only one a real deployment ever uses | Shipping quick sign-in unconditionally would be simpler and would put one-click administrator access on a public page. Tying it to the debugging flag was rejected in research.md: that conflates two decisions a deployment may make independently |

## Phase ordering note for `/speckit-tasks`

User Stories 1 and 2 are both P1, small, and independently testable, and they are the reported
defect. They should be able to ship without waiting for the other four.

One ordering constraint is real rather than organisational: **the translation check (US3) should
land before the sign-in screen and the audit log (US4, US6)**, because both add strings, and
adding strings under a check that cannot see wrong ones is how the `Reference` entry arrived.
