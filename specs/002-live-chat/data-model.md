# Phase 1 Data Model: Live Chat

**Date**: 2026-09-12 | **Plan**: [plan.md](plan.md) | **Spec**: [spec.md](spec.md)

Two stores, split by whether the data is *supposed* to survive:

- **PostgreSQL** — the conversation, every message, and every observation. The record.
- **Redis** — presence and the waiting queue. State that should die with the process that
  held it, because an agent whose server restarted is not online (research.md #3).

## What already exists and is reused

Live chat adds no second way to do anything the MVP already does.

| Existing | How chat uses it |
|---|---|
| `tickets.Ticket` | Every conversation has one. `origin_channel` gains `CHAT`. |
| `tickets.Message` | Every chat message *is* a Message. `channel` gains `CHAT`. |
| `Message.visibility` | A private note is `INTERNAL`. Nothing new is introduced for it. |
| `customers.Contact` | The pre-chat form matches or creates one exactly as the request form does. |
| `ScopedSoftDeleteModel` | Conversations are scoped and soft-deletable like everything else. |
| `auditlog` | Conversation, Observation and Message are all registered. |

## accounts (amended)

### User.Role — a third value
`AGENT`, `SUPERVISOR`, `ADMINISTRATOR` (FR-037).

A Supervisor holds the Agent's permissions plus observation and whispering within their own
department and branch, and is explicitly denied account administration and the audit log.

**Migration note**: no existing account changes role. Agent remains the default, and moving
someone to Supervisor is a deliberate administrative act.

**Review note**: any permission check phrased as "not an Agent" now silently includes
Supervisors. Every existing check is audited in `/speckit-tasks` rather than assumed correct.

## chat

### Conversation
Scoped, soft-deletable, audited.

`ticket` (FK, required), `contact` (FK, required), `assigned_to` (FK to User, nullable),
`state`, `visitor_token_hash`, `started_at`, `assigned_at`, `ended_at`, `ended_by`,
`end_reason`, `last_activity_at`.

- `state`: `WAITING` → `ACTIVE` → `ENDED`. A conversation returns to `WAITING` when an agent
  disconnects past the grace period (FR-034), so the edge is not one-way.
- `visitor_token_hash` stores a hash, never the token. The token is the visitor's only
  credential (research.md #5); storing it in readable form would make the database a list of
  live session keys.
- `end_reason`: `RESOLVED`, `ENDED_BY_AGENT`, `ENDED_BY_VISITOR`, `VISITOR_DISCONNECTED`,
  `IDLE_TIMEOUT` — recorded because "the customer left" and "the agent closed it" are
  different facts about the same ended conversation.
- `ticket` is set at creation so a transcript can never be orphaned (FR-040), and may be
  re-pointed by the agent, at which point the placeholder is soft-deleted (FR-041).

#### State transitions

```text
          assigned                 ended / resolved
WAITING ────────────▶ ACTIVE ─────────────────────▶ ENDED
   ▲                    │
   └────────────────────┘
     agent lost past the grace period (FR-034)
```

A conversation in `WAITING` with no queue entry behind it is abandoned and is closed by the
sweep, so a visitor who leaves does not hold a slot (FR-019).

### Observation
Audited. Not soft-deletable — an observation record is a fact about something that happened,
and there is no state in which it should be hidden from the log.

`conversation` (FK), `observer` (FK to User), `started_at`, `ended_at`.

Exists because watching a colleague's live conversation is an exercise of authority rather
than a neutral read (FR-023). Reading a stored record and watching a person work are
different acts, and only one of them is invisible to the person being watched.

### Message (existing model, extended)
`channel` gains `CHAT`. Nothing else changes.

A chat message is written to the database **before** it is broadcast (research.md #6), so a
crash costs a delivery — which the client refetches — rather than a transcript, which nothing
can reconstruct.

| Kind | direction | visibility | broadcast to |
|---|---|---|---|
| Visitor's message | `INBOUND` | `PUBLIC` | public + staff groups |
| Agent's reply | `OUTBOUND` | `PUBLIC` | public + staff groups |
| Supervisor's whisper | `OUTBOUND` | `INTERNAL` | **staff group only** |

That last row is the feature's security boundary. The customer's socket is never a member of
the staff group, so a whisper is not filtered away from them — there is no route to them at
all (research.md #2).

## Redis (ephemeral, no migrations)

### Presence — `chat:presence:<user_id>`
A hash holding `capacity` and `active_count`, refreshed by a heartbeat and carrying a TTL a
little longer than the heartbeat interval.

No heartbeat, no key, not online. The failure mode corrects itself rather than perpetuating,
which is the whole reason this is not a table.

### Queue — `chat:queue:<department_id>:<branch_id>`
A sorted set scored by arrival timestamp. `ZRANGE` gives longest-waiting-first (FR-017);
`ZRANK` gives a position to show the visitor (FR-016).

Scoped per department and branch because everything else in this system is, and a queue that
ignored scope would route a visitor to an agent who cannot see their tickets.

### Channel layer — `channels_redis`
Group membership for the broadcast groups. Owned by Channels, not by this application.

## Group naming (not stored, but part of the model)

Computed in `apps/chat/services/groups.py` and nowhere else:

- `chat.<conversation_id>.public` — the customer's socket and the assigned agent's.
- `chat.<conversation_id>.staff` — the assigned agent's socket and any observer's.

One module because this split *is* the security boundary, and a boundary computed in three
consumers will eventually be computed three different ways.

## Validation rules drawn from requirements

| Rule | Source |
|---|---|
| A conversation always has a ticket and a contact | FR-003, FR-040 |
| A visitor is never shown a reference before the conversation ends | FR-040 |
| Re-pointing to another ticket soft-deletes the placeholder and audits both | FR-041 |
| An agent is never assigned beyond their capacity | FR-012 |
| An agent cannot go offline holding open conversations | FR-014 |
| An observer cannot send to the customer | FR-022 |
| A whisper is stored `INTERNAL` and reaches no customer-facing output | FR-025 |
| Observation is scoped by department and branch | FR-043 |
| A conversation is offered only while an agent is online | FR-039 |
| Anyone queued when the last agent leaves is moved to the form | FR-042 |
| Arabic content is stored and displayed unchanged | FR-010 |
