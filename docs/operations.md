# Operations — live chat

What this feature needs to be running, what it does under load, and the numbers that were
measured rather than assumed.

## Redis is now required

Before live chat, Redis was a convenience: it backed Celery and the cache, and the product
served tickets without it. That is no longer true. Chat keeps four things in Redis, and each
one stops the feature dead if it is missing:

| What | Where | Without it |
|---|---|---|
| The channel layer | `CHANNEL_LAYERS` | No message reaches any socket. The conversation still records — nothing is lost — but nobody sees anything arrive. |
| Agent presence and capacity | `apps/chat/services/presence.py` | Nobody is ever online, so chat is never offered (FR-039) and the request form is shown instead. |
| The waiting queue | `apps/chat/services/queue.py` | Visitors cannot be queued; with agents free they are still served. |
| Connection liveness | `apps/chat/services/liveness.py` | Every party looks absent, and the sweep ends live conversations. |

The last row is the dangerous one, and it is worth stating plainly: **if Redis is unavailable
the interruption sweep must not run.** A liveness key that cannot be read is indistinguishable
from one that expired, and the sweep would end every live conversation as
`VISITOR_DISCONNECTED`. See "Before a Redis restart" below.

A Redis restart is otherwise a small, defined loss (research.md #3): agents reappear within one
heartbeat, and waiting visitors are handled the way FR-042 already requires — offered the
request form rather than left waiting silently.

## Background schedule

Chat adds three periodic tasks. Celery Beat must be running, not only a worker; without Beat
the workers are idle and three guarantees quietly stop holding.

| Task | Every | Guarantee it upholds |
|---|---|---|
| `close_deserted_desks` | 60s | FR-042 — nobody waits for a desk that has closed. |
| `sweep_interrupted_conversations` | 15s | FR-033, FR-034 — a party who went silent is acted on. |
| `sweep_idle_conversations` | 30s | FR-036 — warn, then close. |

All three are sweeps because absence is the one state that cannot announce itself: a laptop
that shut mid-sentence sends no event. Everything else in chat is event-driven.

## Tunables

Set in `config/settings/base.py`. The spec flags the last two as the numbers most likely to
feel wrong in practice — confirm them with agents before release.

| Setting | Default | Meaning |
|---|---|---|
| `CHAT_DEFAULT_AGENT_CAPACITY` | 3 | Simultaneous conversations per agent. |
| `CHAT_PRESENCE_TTL_SECONDS` | 45 | No heartbeat for this long, not online. |
| `CHAT_RECONNECT_GRACE_SECONDS` | 60 | How long a dropped party may be away. |
| `CHAT_IDLE_WARNING_SECONDS` | 480 | Warn after eight minutes of silence. |
| `CHAT_IDLE_LIMIT_SECONDS` | 600 | Close after ten. |

Two relationships matter more than the values:

- **Presence TTL must stay below the reconnection grace period.** Otherwise a lost agent is
  still a candidate when their conversation is requeued, and it can be handed straight back.
  The code no longer depends on this (`connect_next_waiting` excludes the previous agent), but
  the ordering is what makes the behaviour sensible rather than merely safe.
- **Both client heartbeats are 20s.** Two may be lost before anyone is considered gone. Raising
  a TTL without raising the heartbeat interval is safe; the reverse is not.

## Measured load

`python tools/chat_load_test.py`, recorded 2026-09-13 on the development machine — Python
3.10, SQLite, the in-process fake Redis. **These are shape, not capacity.** Production uses
PostgreSQL and real Redis over a network; re-run against the deployment before trusting any
absolute number.

Scenario: 50 agents at capacity 3 (150 slots), 150 conversations, then 50 more to force
queueing.

```
assigned:                 150 of 150
start    median/p95:      21.0 / 24.8 ms
assign   median/p95:      19.6 / 24.0 ms

oversubscribed by:        50
queue depth:              50
refuse+queue median/p95:   3.8 /  4.9 ms
position     median/p95:   0.044 / 0.084 ms
```

What the numbers say:

- **Assignment is dominated by the database**, not by presence. It claims a Redis slot and
  then locks and writes a row; the ~20ms is the row. Queueing a visitor, which touches no
  locked row, is five times faster.
- **Position lookup is effectively free** (0.044ms). That is the sorted set earning its place:
  FR-016 pushes a position to every waiting visitor whenever the queue moves, so this runs
  once per waiting visitor per change, and anything linear here would have been felt.
- **Nothing degraded at the saturation boundary.** The 150th assignment is no slower than the
  first, and the transition from assigning to queueing costs nothing.

Not covered by this measurement, and worth doing before a busy launch:

- Real Redis latency over a network, which turns each presence check into a round trip.
- Concurrent arrivals. This run is sequential; it measures work per conversation, not
  contention between them. `tests/test_concurrent_agents.py` covers the take race, but only
  for two agents and only against PostgreSQL in CI.
- Sustained socket count. 150 conversations means at least 300 sockets, plus supervisors.

## Before a Redis restart

1. Stop Celery Beat first. This is the important step: with Redis gone, every liveness key
   reads as absent and `sweep_interrupted_conversations` would end every live conversation.
2. Expect agents to show as offline until their next heartbeat (up to 20s).
3. Expect the waiting queue to be empty afterwards. Anyone waiting is offered the request form
   by `close_deserted_desks` on its next run, so nothing is silently dropped — but they are
   not restored to their place.
4. Start Beat again once Redis is serving.

Conversations themselves are unaffected: they live in PostgreSQL, and so does every message.
