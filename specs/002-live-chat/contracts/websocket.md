# Contract: WebSocket

**Date**: 2026-09-12 | **Plan**: [../plan.md](../plan.md)

Three sockets, one per role. Each row is a contract test, written with Channels'
`WebsocketCommunicator` so a test can assert what a *different* socket does or does not
receive — which is the only shape in which FR-021 and FR-025 can honestly be tested.

Frames are HTML fragments for anything rendered (research.md #4), plus small JSON control
frames for state the client holds across fragments (unread counts, connection status).

---

## Visitor socket — `/ws/chat/visitor/`

**Authorization**: a signed token naming exactly one conversation, presented at connect.
Channels' origin validation applies as well. No session — the visitor is anonymous (FR-005).

**Groups joined**: `chat.<id>.public` only. **Never** the staff group. This is the boundary.

| Direction | Frame | Meaning | Requirement |
|---|---|---|---|
| → server | `message` | text the visitor sent | FR-006 |
| → server | `typing` | the visitor is composing | FR-007 |
| → server | `close` | the visitor ended it | FR-009 |
| ← client | `message.html` | a public message, rendered | FR-006 |
| ← client | `typing` | the agent is composing | FR-007 |
| ← client | `state` | waiting / assigned / ended, plus queue position | FR-016 |
| ← client | `ended` | the conversation is over, with a ticket reference | FR-009, FR-040 |

**Refusals**

| Condition | Response |
|---|---|
| No token, bad signature, or expired | Connection refused at handshake |
| Token names a conversation that has ended | Refused; the client shows the ended state |
| Origin is not an allowed host | Refused |
| Messages faster than the rate limit | Frame dropped with a `throttled` notice, connection kept |

**Never sent to this socket**: any frame derived from an `INTERNAL` message; any indication
that an observer is present (FR-021). Both are guaranteed by group membership rather than by
filtering.

---

## Agent socket — `/ws/chat/agent/`

**Authorization**: an authenticated session, role Agent or Supervisor, scoped to their own
department and branch.

**Groups joined**: `chat.<id>.public` **and** `chat.<id>.staff` for each conversation they
hold, plus a personal group for assignment offers.

| Direction | Frame | Meaning | Requirement |
|---|---|---|---|
| → server | `message` | a public reply to the customer | FR-006 |
| → server | `typing` | the agent is composing | FR-007 |
| → server | `close` | end, optionally resolving the ticket | FR-009, FR-029 |
| → server | `online` / `offline` | presence, refused if holding conversations | FR-011, FR-014 |
| → server | `heartbeat` | refreshes the presence TTL | research.md #3 |
| → server | `attach_ticket` | re-point the conversation at an existing ticket | FR-038, FR-041 |
| ← client | `message.html` | a message, public or internal, rendered for staff | FR-006, FR-026 |
| ← client | `assigned` | a new conversation, with customer context | FR-004, FR-015 |
| ← client | `unread` | per-conversation unread counts | FR-013 |
| ← client | `typing` | the visitor is composing | FR-007 |
| ← client | `ended` | this conversation closed, and why | FR-033 |

**Refusals**

| Condition | Response |
|---|---|
| Not authenticated, or session ended (MVP FR-026) | Refused at handshake, and existing sockets closed |
| Conversation outside their department or branch | Refused as not-found, never as forbidden (MVP FR-024) |
| `offline` while holding open conversations | Refused with the count still open (FR-014) |
| Assignment beyond capacity | Never offered; capacity is claimed in the same transaction as assignment (FR-012) |

---

## Supervisor socket — `/ws/chat/supervise/`

**Authorization**: an authenticated session, role **Supervisor or Administrator**, and the
conversation must be within their department and branch (FR-043).

**Groups joined**: `chat.<id>.staff` only. Not the public group — an observer is not a
participant, and this is why they cannot become one by accident.

| Direction | Frame | Meaning | Requirement |
|---|---|---|---|
| → server | `whisper` | a private note to the agent | FR-024 |
| ← client | `message.html` | every message in the conversation, public and internal | FR-020 |
| ← client | `typing` | either party composing | FR-020 |
| ← client | `ended` | the conversation closed | FR-020 |

**Refusals — the ones that matter**

| Condition | Response | Requirement |
|---|---|---|
| Role is Agent | Refused at handshake | FR-037 |
| Conversation out of scope | Refused as not-found | FR-043 |
| A `message` frame (customer-directed) | **Rejected outright**, never forwarded | FR-022 |

**On connect**: an `Observation` row is written. On disconnect it is closed. Watching a
colleague is a recorded act (FR-023).

---

## Invariants every contract test asserts

1. A `whisper` reaches the agent's socket and **not** the visitor's — asserted by opening both
   and confirming the visitor's receives nothing at all, not merely nothing internal.
2. A supervisor connecting produces **no frame of any kind** on the visitor's socket (FR-021).
3. A `message` frame sent by a supervisor is rejected and never appears on any socket.
4. A message is present in the database **before** it appears on any socket (research.md #6).
5. An out-of-scope conversation is refused identically to one that does not exist.
