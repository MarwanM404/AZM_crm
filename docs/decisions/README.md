# Architecture Decision Records

Each record captures one decision, the context that forced it, and the consequences the team
accepted by taking it. Records are immutable once accepted: a decision that changes gets a new
record that supersedes the old one, rather than an edit that erases the history.

**Status values**: `Proposed` (recommended, awaiting confirmation), `Accepted` (decided),
`Superseded by ADR-NNN`, `Rejected`.

| ADR | Decision | Status | Roadmap decision |
|-----|----------|--------|------------------|
| [001](001-web-framework.md) | Django as the web framework | Accepted | #1 |
| [002](002-database.md) | PostgreSQL as the database | Proposed | #2 |
| [003](003-frontend-approach.md) | Server-rendered Django with htmx and Alpine.js | Accepted | #3 |
| [004](004-tenancy-scoping.md) | Explicit department and branch scoping | Proposed | #4 |
| [005](005-background-jobs.md) | Celery with Redis | Proposed | #5 |
| [006](006-deployment-target.md) | Local for development; production target deferred | Accepted | #8 |
| [007](007-realtime-transport.md) | Django Channels over ASGI for real-time transport | Accepted | — |
| [008](008-chat-client.md) | htmx over WebSocket for the chat client | Accepted | — |

Roadmap decisions #6 (WhatsApp and SMS providers) and #7 (AI provider and data policy) are
deliberately deferred; both belong to phases outside the MVP.

ADR-007 and ADR-008 belong to [002-live-chat](../../specs/002-live-chat/spec.md) rather than to
a roadmap decision. ADR-008 answers the question ADR-003 deliberately left open for this phase.
