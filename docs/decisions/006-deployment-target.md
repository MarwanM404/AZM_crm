# ADR-006: Deployment target

**Status**: Accepted for development; production target **deferred**
**Date**: 2026-09-12
**Roadmap decision**: #8
**Relates to**: [ADR-002](002-database.md), [ADR-005](005-background-jobs.md)

## Context

The remaining release tasks depend on where this system runs. ADR-005 assumes the environment
can run persistent worker processes and a Redis instance; ADR-002 assumes a PostgreSQL with
exercised backups. Both assumptions need confirming against a real environment rather than a
preference.

Deployment also determines how the constitution's rule on secrets is honoured in practice —
supplied through environment configuration or a secret manager, never committed — and, because
the system holds customer personal data, whether data residency is constrained by policy or
contract.

## Decision

**For now: the developer's own machine.** PostgreSQL is installed locally and the application
has been run against it. This is a real and sufficient decision for the current stage — the
system is not yet taking requests from customers — and recording it beats leaving the record
blank while work continues around it.

**A production target is deliberately not chosen yet.** No customer data is at stake until one
is, so the choice can wait for the people who will operate the system rather than be settled by
whoever is writing code that week.

## Consequences

**Now true**

- Development and testing run against PostgreSQL, matching ADR-002, so nothing is being proved
  against an engine the project does not intend to use.
- The automated suite still runs on SQLite for speed; CI runs it against PostgreSQL
  (`config/settings/ci.py`), which is where the guarantees needing row-level locking are
  actually exercised.
- Secrets live in a local `.env`, which is gitignored. Nothing about that changes when a
  production target is chosen — only where the values come from.

**Still blocked, and blocking release**

| Task | Why it cannot be done yet |
|---|---|
| T144 encryption at rest | A property of the host — an encrypted volume, or a managed database with encryption enabled. There is nothing to configure until a host exists. |
| T145 mail routing | Needs a deliverable address and an inbound route on a domain the organization controls. See [docs/email-setup.md](../email-setup.md). |
| T146 backup and restore drill | Needs a production database to drill against. A drill on a laptop proves the commands run, not that the procedure works. |

**What this means in practice**: the system can be demonstrated and worked on, but must not
hold a real customer's data until T144 and T146 are done. Personal data on an unencrypted,
unbackuped machine is the specific risk being deferred here, and it is being deferred
knowingly rather than overlooked.

## When the production decision is made

Whoever makes it needs to answer four questions; each maps to work that is already written and
waiting:

1. **Who operates it** — your team, a client's IT department, or a managed platform.
2. **Can it run persistent worker processes, Redis, and an ASGI server?** ADR-005 assumes the
   first two; [ADR-007](007-realtime-transport.md) added the third when live chat adopted
   Django Channels, and it also made Redis required rather than merely important — without it
   there is no chat at all. Some constrained hosting cannot run an ASGI process or hold
   long-lived connections, which would force both decisions to be revisited before
   implementation rather than after.
3. **Where may customer personal data physically reside?** Contractual or regulatory limits
   settle this, not convenience.
4. **How do secrets reach the running application?** Environment variables from the platform,
   or a secret manager. Committing them is prohibited by the constitution.

This record is superseded by a new ADR when that decision is made, rather than edited — the
fact that a local-only stage existed is part of the history.
