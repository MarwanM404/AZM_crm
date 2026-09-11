# ADR-006: Deployment target

**Status**: Draft
**Date**: 2026-09-11
**Roadmap decision**: #8
**Relates to**: [ADR-002](002-database.md), [ADR-005](005-background-jobs.md)

## Context

The remaining decisions depend on where this system runs. ADR-005 assumes the environment can run
persistent worker processes and a Redis instance; ADR-002 assumes a managed or self-hosted
PostgreSQL with exercised backups. Both assumptions need confirming against reality rather than
preference.

Deployment also determines how the constitution's rule on secrets is honoured in practice: secrets
are supplied through environment configuration or a secret manager, never committed.

Additional factors specific to this system: customer personal data means data residency may be
constrained by policy or contract, and the audit trail implies retention and backup obligations.

## Decision

<!-- TODO(human): record the deployment target and the constraints behind it. -->

## Consequences

To be completed once the decision above is recorded.
