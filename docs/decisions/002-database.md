# ADR-002: PostgreSQL as the database

**Status**: Proposed
**Date**: 2026-09-11
**Roadmap decision**: #2
**Relates to**: [ADR-001](001-web-framework.md)

## Context

The constitution requires a relational database with enforced foreign-key constraints. The MVP
specification requires search and filtering across tickets (FR-011), an audit trail storing the
before and after values of arbitrary changed fields (FR-027), and storage of Arabic content without
corruption at every boundary (FR-035). The knowledge base in a later phase adds full-text search
over bilingual content.

## Decision

Use PostgreSQL.

## Consequences

**Gained**

- Foreign keys, check constraints, and transactional DDL, satisfying the constitutional requirement
  and supporting the "multi-step writes in one transaction" rule directly.
- A `JSONB` column type suited to audit before/after payloads, where the changed fields differ per
  entity. The alternative is one audit row per field, which multiplies row counts on every write.
- Full-text search with configurable language handling, which matters for Arabic and becomes load
  bearing when the knowledge base arrives. Arabic search quality needs testing early regardless;
  Postgres at least makes it tunable without a separate search service.
- First-class support in Django, including a dedicated `django.contrib.postgres` module.

**Accepted costs**

- One more service to operate, back up, and restore. Backup and restore must be exercised, not
  assumed, before the MVP carries real customer data.
- Arabic full-text search configuration is not automatic. Budget time in the knowledge-base phase
  to evaluate it against real content.

## Alternatives considered

- **MySQL or MariaDB**: workable and widely deployed. Weaker JSON handling for the audit payload and
  a less capable full-text story for the later knowledge base.
- **SQLite**: adequate for local development and tests, and it will be used there. Not suitable for
  concurrent production writes at the volumes in SC-009 and SC-010.

## Open

This record is `Proposed`. It becomes `Accepted` when the team confirms there is no operational
constraint (existing database estate, hosting limitation, or administration expertise) that favours
a different engine.
