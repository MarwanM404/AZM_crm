# Implementation Plan: Live Chat

**Branch**: `002-live-chat` | **Date**: 2026-09-12 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-live-chat/spec.md`

## Summary

Live chat over WebSockets, served by Django Channels on ASGI, with the interface rendered on
the server and delivered as HTML fragments through htmx's WebSocket extension — the same
convention ADR-003 set for the rest of the product, extended rather than replaced.

The design decision that matters most is not the transport. It is that each conversation has
**two separate broadcast groups**: one carrying the customer's socket, one staff-only. A
supervisor's private note is published to the staff group, which the customer's socket has
never joined. The leak that FR-025 prohibits is not prevented by remembering to filter — it is
prevented because there is no wire from the whisper to the customer.

Presence and the waiting queue live in Redis with expiry; the conversation and every message
live in PostgreSQL. Messages are written to the database **before** they are broadcast, so a
crash loses a delivery rather than a transcript.

New decisions are recorded in [ADR-007](../../docs/decisions/007-realtime-transport.md) and
[ADR-008](../../docs/decisions/008-chat-client.md).

## Technical Context

**Language/Version**: Python 3.10 (3.12 target — see the MVP plan's note)

**Primary Dependencies**: existing stack plus `channels`, `channels-redis`, and `uvicorn`
(ASGI server). Client side: `htmx-ext-ws` alongside the htmx and Alpine.js already vendored.

**Storage**: PostgreSQL for conversations, messages and observations — everything that must
survive. Redis for presence, the waiting queue, and the Channels layer — everything that
*should not* survive a restart.

**Testing**: `pytest` with `pytest-asyncio` and Channels' `WebsocketCommunicator` for consumer
behaviour; Playwright driving **two real browsers at once** for the genuinely two-party
scenarios, which no single-client test can express.

**Target Platform**: Linux server, now ASGI rather than WSGI. This changes how the application
is served and is the reason ADR-007 exists.

**Performance Goals**: a message reaches the other party in under 2 seconds (SC-002); an
available agent is reached in under 30 seconds (SC-001); an agent holds 3 simultaneous
conversations (SC-006); the assumed 50-agent population from the MVP's research still applies.

**Constraints**: a private note must be undeliverable to a customer, not merely unrendered;
observation must be invisible to the customer and scoped to the observer's department;
everything bilingual with correct right-to-left layout; the visitor is anonymous, so their
socket is authorized by a signed conversation token rather than a session.

**Scale/Scope**: 50 agents × 3 conversations = 150 concurrent conversations, each with up to
three sockets (customer, agent, supervisor). Roughly 400 concurrent WebSocket connections at
the ceiling — small, but it is the first part of this system where a connection count matters
at all.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

### I. Test-First (NON-NEGOTIABLE)

| Requirement | How this plan satisfies it |
|---|---|
| Test precedes implementation | `/speckit-tasks` orders every consumer, service and view behind its failing test, as in the MVP. |
| Contract test per public surface | [contracts/](contracts/) enumerates every WebSocket message type and HTTP endpoint; each gets a test. |
| The hard part is testable | Channels' `WebsocketCommunicator` lets a test open a socket, send, and assert what a *different* socket does or does not receive — which is exactly the shape of FR-021 and FR-025. |

**Status**: PASS

### II. Data Integrity & Auditability

| Requirement | How this plan satisfies it |
|---|---|
| Audit entry on every mutation | Conversations, messages and observations are audited models; `Observation` exists so that watching a colleague is itself a recorded act (FR-023). |
| Transactions for multi-step writes | Assignment (claim capacity + attach agent) is one transaction with a locked row, like the MVP's ticket take. |
| Nothing is lost | A message is persisted before it is broadcast. A crash therefore costs a delivery, which the client can re-fetch, rather than a transcript, which nothing can reconstruct. |
| Reversible migrations | Django migrations, reviewed separately. |

**Status**: PASS

### III. Security & Access Control

| Requirement | How this plan satisfies it |
|---|---|
| Deny by default | A socket is rejected at connect time unless it proves it belongs: staff by session, visitor by signed token naming one conversation. |
| Least privilege | Supervisor is a third role that observes and coaches but cannot administer (FR-037). An observer's socket is joined to the staff group read-only and its consumer refuses customer-directed sends (FR-022). |
| Scope | Observation is filtered by department and branch at connect time, and an out-of-scope conversation is refused as not-found (FR-043, MVP FR-024). |
| Secrets outside the repository | Unchanged: environment configuration. |
| The private-note boundary | Group separation, described in the Summary. Reinforced by the existing `visibility` field and the existing customer-facing filter, so there are three layers rather than one. |

**Status**: PASS

### IV. Simplicity & YAGNI

| Dependency | Justified by | Simpler alternative rejected because |
|---|---|---|
| `channels` + `channels-redis` | FR-006 two-second delivery, FR-007 typing indicators | Polling at the required interval costs a request per client per two seconds and cannot express typing; long-polling under WSGI holds a worker per waiting visitor. See research.md #1. |
| `uvicorn` (ASGI) | Persistent connections cannot be served by WSGI | None: this is a property of the protocol, not a preference. |
| `htmx-ext-ws` | Renders server-side HTML over the socket | A JavaScript client would split the translation catalog in two and move rendering off the server, both of which ADR-003 rejected for good reasons that have not changed. |

No speculative abstraction: there is no pluggable transport layer, no message-broker
indirection, and no chat "engine" — one consumer per role, and the existing models.

**Status**: PASS

## Project Structure

### Documentation (this feature)

```text
specs/002-live-chat/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── websocket.md
│   └── http-endpoints.md
├── checklists/requirements.md
├── spec.md
└── tasks.md             # Created later by /speckit-tasks
```

### Source Code (repository root)

```text
config/
├── asgi.py                  # becomes a ProtocolTypeRouter: HTTP to Django, WS to Channels
└── settings/base.py         # ASGI_APPLICATION, CHANNEL_LAYERS

apps/chat/                   # the new app
├── models.py                # Conversation, QueueEntry (durable part), Observation
├── consumers/
│   ├── visitor.py           # the customer's socket
│   ├── agent.py             # the agent's socket
│   └── supervisor.py        # observation and whisper; refuses customer-directed sends
├── routing.py               # websocket_urlpatterns
├── services/
│   ├── presence.py          # Redis-backed online/capacity, TTL heartbeat
│   ├── queue.py             # Redis sorted set, longest-waiting first
│   ├── assignment.py        # claim capacity and attach an agent, in one transaction
│   ├── groups.py            # THE group-name rules: public vs staff, one place only
│   └── transcript.py        # write the conversation onto its ticket when it ends
├── views.py                 # the public widget, the agent console, the supervisor view
└── urls.py

apps/accounts/               # Supervisor role added here (FR-037)
apps/tickets/                # Message gains a CHAT channel; nothing else changes

templates/chat/
├── widget.html              # the visitor panel, embeddable on the public site
├── console.html             # the agent's multi-conversation console
└── partials/                # the fragments pushed over the socket

tests/
├── test_whisper_isolation.py   # the cross-cutting invariant: FR-021, FR-025
└── e2e/test_two_party_chat.py  # two real browsers, one conversation
```

**Structure Decision**: a new `apps/chat` rather than an extension of `apps/tickets`, because
a conversation has its own lifecycle, its own transport, and its own consumers, while a ticket
remains what it was. The link between them is one foreign key and one service
(`transcript.py`), which keeps the MVP's ticket code untouched.

`services/groups.py` exists as its own module for one reason: the public/staff group split is
the security boundary of this feature, and a boundary computed in three consumers is a boundary
that will eventually be computed three different ways.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Moving the whole application from WSGI to ASGI | A persistent connection cannot be served by WSGI, and running a second server just for sockets means two deployments, two configurations, and a session cookie shared across both. | Running Channels alongside WSGI was considered and rejected in research.md #1: one ASGI server serving both protocols is the simpler end state, even though the migration itself is the larger change. |
| Redis holding state (presence, queue) | Presence is *supposed* to be ephemeral — an agent whose server restarted is not online. | A database table would be durable, which is precisely wrong: a crashed agent's row says "online" forever, and nothing clears it. See research.md #3. |

## Post-Design Constitution Re-Check

*Re-evaluated after Phase 1 design artifacts were produced.*

| Principle | Result | Evidence from the design |
|---|---|---|
| I. Test-First | PASS | Every WebSocket frame in [contracts/websocket.md](contracts/websocket.md) is a test, and the contract states five invariants that can only be asserted by opening two sockets at once. |
| II. Data Integrity & Auditability | PASS | Message before broadcast; Observation is its own audited record; assignment claims capacity in one transaction. |
| III. Security & Access Control | PASS | The whisper boundary is group membership rather than filtering, backed by the existing visibility field and customer-facing filter — three layers. Out-of-scope conversations are refused as not-found. |
| IV. Simplicity & YAGNI | PASS | Three consumers and one new app; no pluggable transport, no message-broker indirection, no chat engine. The existing Message model is extended by one channel value rather than duplicated. |

**Design decisions that tightened requirements**

- A whisper is not *filtered* from the customer — the customer's socket never joins the group
  it is published to. FR-025 becomes a property of the wiring rather than of remembering.
- The visitor's token is stored **hashed**. It is their only credential, and a readable column
  would make the database a list of live session keys.
- `Conversation.state` can return from `ACTIVE` to `WAITING`, because FR-034 requires a lost
  agent's conversation to be requeued rather than ended.
- `end_reason` is recorded: "the customer left" and "the agent closed it" are different facts
  about the same ended conversation, and only one of them is a service problem.
- Any permission check phrased as "not an Agent" silently grants Supervisors administrator
  powers. Every existing check is audited in `/speckit-tasks` rather than assumed.

**Gate result**: PASS. Ready for `/speckit-tasks`.
