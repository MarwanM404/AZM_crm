# ADR-008: htmx over WebSocket for the chat client

**Status**: Accepted
**Date**: 2026-09-12
**Relates to**: [ADR-003](003-frontend-approach.md), [ADR-007](007-realtime-transport.md)

## Context

[ADR-003](003-frontend-approach.md) chose server-rendered Django with htmx for the MVP and
explicitly left one question open:

> Whether its client is htmx over WebSocket or a small Vue component is deferred to that phase
> and does not need deciding now.

This is that phase. Live chat is the most interactive screen in the product and the strongest
case anyone will make for a component framework.

## Decision

Use **htmx's WebSocket extension**, receiving server-rendered HTML fragments over the socket,
with **Alpine.js** for state the client holds across fragments — the composer, unread badges,
connection status.

Vue is not adopted.

## Consequences

**Gained**

- One translation catalog still serves screens, email and now chat. This was ADR-003's primary
  concern, and bilingual-at-launch made it permanent rather than temporary.
- Rendering stays on the server, so authorization stays where the data is. A fragment pushed
  over a socket is produced by ordinary Django code with ordinary scope checks.
- No second build pipeline, no client bundle to version, no API surface invented for one
  screen.

**Accepted costs**

- **Unread counts across several conversations are the strained case.** That state outlives any
  one fragment and is the one thing this approach does not do naturally. Alpine holds it, keyed
  by conversation, updated by a small JSON control frame alongside the HTML ones.
- Two frame kinds on one socket — HTML for anything rendered, JSON for client state — is
  marginally more to explain than a single JSON protocol would be.

**If this proves wrong**

The awkwardness is isolated to the console's unread badges. That is the one place a component
framework would earn its keep, and it can be replaced without touching the consumers, the
services, or any other screen. This decision is reversible in a way that "adopt Vue across the
product" would not have been.

## Alternatives considered

- **A Vue component for the chat pane.** Genuinely the stronger choice if the client needed
  rich local state. Rejected because chat's state is a message list, a typing flag, an unread
  count and a connection status — and the cost is splitting the translation catalog in two for
  one screen, which is exactly what ADR-003 weighed most heavily.
- **A plain JavaScript WebSocket client rendering JSON.** Fewer dependencies than Vue, but it
  moves rendering to the client and takes the translation catalog with it, incurring ADR-003's
  main cost while gaining none of Vue's benefits.
