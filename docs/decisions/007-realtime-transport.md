# ADR-007: Django Channels over ASGI for real-time transport

**Status**: Accepted
**Date**: 2026-09-12
**Relates to**: [ADR-001](001-web-framework.md), [ADR-005](005-background-jobs.md),
[spec 002-live-chat](../../specs/002-live-chat/spec.md)

## Context

Live chat is the first synchronous feature in a product that is otherwise entirely
asynchronous. FR-006 requires a message to reach the other party within two seconds and FR-007
requires typing indicators. Both need the server to push to a client that is already connected.

The application currently runs WSGI, which cannot hold a connection without holding a worker.

## Decision

Adopt **Django Channels**, served by **uvicorn over ASGI**, with **Redis** as the channel
layer. The whole application moves to ASGI: one server process handles both ordinary HTTP and
WebSocket.

## Consequences

**Gained**

- Server-initiated delivery, which is what the requirement actually asks for.
- Django's existing synchronous views keep working unchanged under ASGI, so this is a change to
  how the application is served rather than a rewrite of what exists.
- Redis was already justified for background work in ADR-005, and this is the third use that
  decision anticipated.

**Accepted costs**

- **The ORM is synchronous and consumers are asynchronous.** Every database touch inside a
  consumer goes through `database_sync_to_async`. This is the real cost and the likeliest
  source of subtle bugs, so the design keeps business logic in ordinary synchronous services
  and leaves consumers doing nothing but transport.
- Deployment changes shape: an ASGI server rather than a WSGI one. This lands on
  [ADR-006](006-deployment-target.md), which is still deferred, and the requirement is now
  firmer — the eventual host must run an ASGI process, not merely a WSGI one.
- Redis moves from important to **required**. Without it there is no chat, where previously its
  loss only delayed background jobs.

## Alternatives considered

- **Polling every two seconds.** Satisfies the letter of FR-006 with no new infrastructure.
  Rejected: at 150 concurrent conversations it is roughly 225 requests a second mostly
  returning nothing, and a typing indicator sampled every two seconds reports that someone
  *was* typing, which is worse than showing nothing.
- **Server-Sent Events over WSGI.** Genuinely simpler — one-way push, sending over ordinary
  POSTs. Rejected because an open SSE connection still occupies a WSGI worker: fifty idle
  agents would hold fifty workers doing nothing.
- **Channels beside the existing WSGI server**, sockets on one and pages on the other.
  Rejected in favour of a single ASGI server. Two deployments, two configurations and a session
  cookie that must work identically across both is more moving parts than the migration it
  avoids.
