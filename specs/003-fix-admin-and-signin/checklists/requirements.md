# Specification Quality Checklist: Administration visibility, bilingual correctness, and the sign-in screen

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-13
**Feature**: [spec.md](../spec.md)

## Content Quality

- [X] No implementation details (languages, frameworks, APIs)
- [X] Focused on user value and business needs
- [X] Written for non-technical stakeholders
- [X] All mandatory sections completed

## Requirement Completeness

- [X] No [NEEDS CLARIFICATION] markers remain
- [X] Requirements are testable and unambiguous
- [X] Success criteria are measurable
- [X] Success criteria are technology-agnostic (no implementation details)
- [X] All acceptance scenarios are defined
- [X] Edge cases are identified
- [X] Scope is clearly bounded
- [X] Dependencies and assumptions identified

## Notes

### What validation actually found

This spec was written directly from a reproduction session, and the first pass showed exactly
the contamination you would expect from that: the findings arrived carrying their file paths
and mechanisms, and several came through into the requirements.

**Pass 1 — implementation details, seven instances.** All of the same kind: naming *how* rather
than *what*.

| Was | Now |
|---|---|
| "not marked fuzzy, so the catalog tooling…" | "nothing flags the entry as uncertain, so the automated checks…" |
| "by any route, including the command line" | "including routes that bypass the administration screens" |
| "as a build-time check" | "as an automated check that fails" |
| "switchable on by an environment variable" | "no deployment setting, override or mistake may switch it on" |
| SC-004 "fails the build" | "is rejected automatically, before anyone sees it" |
| SC-002 "without editing the database directly" | "without manipulating stored data by hand" |
| "the state a command-line account-creation tool leaves behind" | "the state the very first account on a new installation is left in" |

**Pass 2 — one requirement was not testable.** FR-021 originally read "MUST treat 'a check
found nothing' and 'there is nothing to find' as different statements", which is an observation
rather than a requirement: there is no way to fail it. Rewritten as something that can be
checked — every check this feature adds must be demonstrated to fail when its defect is
reintroduced deliberately. That is a procedure, not a sentiment.

Pass 3 found nothing further.

### Deliberate choices a reviewer should check rather than assume

- **FR-002 refuses rather than corrects.** An administrator who deliberately chose another
  department meant something by it, and silently moving the account into their own scope would
  be a second invisible outcome — the exact failure this spec exists to remove. In Assumptions.
- **No [NEEDS CLARIFICATION] markers**, which is unusual and worth explaining rather than
  treating as a sign of quality. The five defects were reproduced before the spec was written,
  so questions that would normally be open here were settled by observation. The one genuine
  open product question is deliberately *excluded*: whether an anonymous visitor should get
  Arabic or English by default. Today they get English, consistently with the public request
  form, and that is intentional — changing it is a product decision, not a defect, and putting
  it in a defect spec would smuggle it past that decision.
- **FR-020 and FR-021 are constraints, not features.** Neither will appear as a screen. They
  exist so the next instance of either failure is caught by a rule rather than by a customer,
  and they should be read as conditions on how everything else here is built.

### Known limit, stated rather than designed around

FR-010 catches a translation that introduces a placeholder its source lacks — a precise rule
that found the one real offender in both catalogs with no false positives. It does **not** catch
a translation that is simply wrong: a fluent Arabic sentence with the wrong meaning passes
every check in this spec. User Story 3, scenario 5 makes the human review a recorded step for
that reason. A spec that claimed otherwise would repeat the mistake it was written to fix.
