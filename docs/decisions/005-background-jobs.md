# ADR-005: Celery with Redis for background work

**Status**: Proposed
**Date**: 2026-09-11
**Roadmap decision**: #5
**Relates to**: [spec FR-006, FR-013, FR-016](../../specs/001-mvp-ticket-desk/spec.md)

## Context

The MVP needs work that must not run inside a web request:

- Inbound email must be collected and matched to tickets (FR-013).
- Outbound email must be sent with retries, and failures surfaced on the ticket (FR-016).
- The public form must be protected against abusive submission volume (FR-006), which needs a shared
  counter rather than per-process state.

Immediately after the MVP, live chat adds WebSocket transport and presence state, and the SLA phase
adds scheduled timers and escalation.

## Decision

Use **Celery** with **Redis** as the broker, plus **Celery Beat** for scheduled work.

## Consequences

**Gained**

- Redis earns its place three times over: Celery broker, rate-limit counter for FR-006, and the
  channel layer for Django Channels when live chat arrives. One operational component, three uses,
  which is why this is not a Principle IV violation despite adding infrastructure.
- Retries with backoff are a framework feature, which FR-016 needs rather than wants.
- Celery Beat covers the SLA timers and escalation checks the next phase requires, so that phase
  adds tasks rather than infrastructure.

**Accepted costs**

- Two more processes to run and monitor in every environment, including development. Document the
  local setup in Phase 0 or developers will skip the worker and write code that silently never runs.
- Redis is now a production dependency whose failure degrades email and rate limiting. Decide what
  the system does when the broker is unavailable: queued email must not be lost silently.
- Task code runs outside the request cycle, so the acting user is not implicit. Every task that
  writes to a customer record must carry the actor explicitly to satisfy FR-027, or the audit trail
  will record a system user for work a person initiated.

## Alternatives considered

- **django-q2 or huey**: simpler, fewer moving parts, and genuinely sufficient for the MVP alone.
  Rejected because the live chat phase brings Redis in regardless, at which point the simpler queue
  is a second mechanism rather than a saving.
- **Cron plus management commands**: no broker and no worker, but no retries, no backoff, and poor
  visibility into failures. Insufficient for FR-016.
- **Database-backed queue**: avoids Redis, adds write load to the database that SC-009 already asks
  to stay responsive under.

## Open

This record is `Proposed`. Confirm that the deployment target (ADR-006) can run persistent worker
processes and a Redis instance. Some constrained hosting cannot, which would force a rethink.
