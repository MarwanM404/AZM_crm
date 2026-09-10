<!--
Sync Impact Report
Version change: [CONSTITUTION_VERSION] (unpopulated template) → 1.0.0
Bump rationale: Initial ratification. All placeholder tokens replaced with concrete
governance; first enforceable version of the document.
Modified principles:
  - [PRINCIPLE_1_NAME] → I. Test-First (NON-NEGOTIABLE)
  - [PRINCIPLE_2_NAME] → II. Data Integrity & Auditability
  - [PRINCIPLE_3_NAME] → III. Security & Access Control
  - [PRINCIPLE_4_NAME] → IV. Simplicity & YAGNI
Added sections:
  - Technology & Platform Constraints (was [SECTION_2_NAME])
  - Development Workflow & Quality Gates (was [SECTION_3_NAME])
  - Governance (populated)
Removed sections:
  - [PRINCIPLE_5_NAME] / [PRINCIPLE_5_DESCRIPTION] — the project adopted four principles;
    the fifth template slot was not used.
Deferred TODOs: none.
-->

# AZM CRM Constitution

## Core Principles

### I. Test-First (NON-NEGOTIABLE)

Tests MUST be written before the implementation they cover. The cycle is strict:
write the test, confirm it fails for the right reason, then implement until it passes,
then refactor. Merging implementation code that was never preceded by a failing test is
a violation, regardless of the final coverage number.

Every bug fix MUST begin with a regression test that reproduces the defect. Every public
API surface (HTTP endpoint, service function, background job entry point) MUST have at
least one contract test asserting its inputs, outputs, and error responses.

Rationale: A CRM holds the customer records the business runs on. Untested changes to
that data path are discovered by users, not by developers, and are expensive to unwind.

### II. Data Integrity & Auditability

Customer records are the system of record and MUST be treated as such:

- Every mutation of a customer, contact, deal, or account record MUST be validated against
  an explicit schema at the boundary before it reaches persistence.
- Every mutation MUST write an audit entry capturing actor, timestamp (UTC, ISO 8601),
  entity, action, and the before/after values of changed fields.
- Deletion of customer-facing records MUST be soft by default. Hard deletion is reserved
  for legally mandated erasure and MUST be an explicit, logged operation.
- Multi-step writes that must succeed or fail together MUST run inside a single database
  transaction.
- Schema changes MUST ship as reversible, version-controlled migrations. No manual edits
  to a production schema.

Rationale: Auditability is what lets the team answer "who changed this and when" during a
customer dispute, and it is a precondition for most data-protection obligations.

### III. Security & Access Control

- Access control is deny-by-default. Every endpoint and every background action MUST
  authorize the acting principal explicitly; absence of a check is a failure, not a
  permissive default.
- Roles MUST follow least privilege. A role receives the narrowest permission set that
  lets it do its job.
- Secrets (credentials, API keys, tokens, connection strings) MUST NOT appear in the
  repository, in logs, or in error messages. They are supplied through environment
  configuration or a secret manager.
- Personally identifiable information MUST be encrypted in transit (TLS) and at rest.
- Logs and error reports MUST NOT contain raw PII or secret material.
- All external input MUST be validated and parameterized. String-built SQL is prohibited.
- Dependencies MUST be pinned, and known-vulnerable versions MUST be upgraded or removed
  before release.

Rationale: The system concentrates personal and commercial data about real customers. A
single missing authorization check exposes all of it.

### IV. Simplicity & YAGNI

Build what the current specification requires and no more. Speculative abstraction,
unused configuration switches, and premature generalization are defects.

- Prefer the standard library and the framework already in use over a new dependency. Each
  new dependency MUST be justified in the plan that introduces it.
- Prefer one clear implementation over a pluggable layer with a single implementation.
- Any deviation from the simplest workable design MUST be recorded, with its reason, in
  the feature's plan before the code is written.

Rationale: Complexity added in advance of a real requirement is paid for on every later
change, and usually by someone other than the person who added it.

## Technology & Platform Constraints

- The backend is written in Python. The web UI is served as a browser-based client.
- The specific web framework, database engine, and frontend framework are selected per the
  feature plan and MUST remain consistent across the project once chosen. Introducing a
  second framework in the same layer requires an amendment to this section.
- Persistent data lives in a relational database with enforced foreign-key constraints.
- All application configuration is supplied by environment variables. Configuration MUST
  NOT be hardcoded or committed.
- All timestamps are stored in UTC. Localization happens at the presentation layer only.
- Python code MUST pass the project's configured formatter, linter, and type checker before
  merge.

## Development Workflow & Quality Gates

- Work follows the Spec Kit flow: specify, then plan, then tasks, then implement. Code MUST
  NOT be written for a feature that has no approved specification.
- All changes reach the main branch through review. Self-merging without review is not
  permitted.
- A change is mergeable only when all of the following hold:
  1. The automated test suite passes.
  2. Formatter, linter, and type checker report no errors.
  3. New behavior is covered by tests written before the implementation.
  4. Any new customer-data mutation writes an audit entry.
  5. Any new endpoint or action performs an explicit authorization check.
  6. No secrets or PII are present in the diff, including fixtures and logs.
- Reviewers MUST verify compliance with each principle above and MUST reject changes that
  add unjustified complexity.
- Database migrations MUST be reviewed separately from application logic and MUST be
  verified as reversible.

## Governance

This constitution supersedes all other development practices, conventions, and habits in
this project. Where a style guide, a template, or an agent instruction conflicts with it,
this document wins.

**Amendment procedure**: Amendments are proposed as a change to this file, stating the
motivation, the exact text change, and the migration impact on existing code. An amendment
takes effect when reviewed and merged. Amendments that invalidate existing code MUST list
the remediation steps and a deadline.

**Versioning policy**: This document is versioned as MAJOR.MINOR.PATCH.

- MAJOR: a principle is removed or redefined in a way that invalidates prior compliance.
- MINOR: a principle or governing section is added, or existing guidance is materially
  expanded.
- PATCH: clarification, wording, or typo fixes with no change in meaning.

**Compliance review**: Every review verifies compliance against the gates above. Violations
block the merge. A violation that must ship anyway requires a written justification in the
pull request and an accompanying amendment proposal or remediation issue. This constitution
is re-read at the start of each feature's planning step; runtime development guidance for
agents lives in `CLAUDE.md`.

**Version**: 1.0.0 | **Ratified**: 2026-09-11 | **Last Amended**: 2026-09-11
