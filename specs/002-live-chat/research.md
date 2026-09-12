# Phase 0 Research: Live Chat

**Date**: 2026-09-12 | **Plan**: [plan.md](plan.md) | **Spec**: [spec.md](spec.md)

## 1. Real-time transport

**Decision**: Django Channels over ASGI, with Redis as the channel layer. The whole
application moves to ASGI and one server handles both HTTP and WebSocket.

**Rationale**: FR-006 requires a message to arrive within two seconds and FR-007 requires
typing indicators. Both need the server to push, and WSGI cannot hold a connection without
holding a worker. Channels is the mature answer in Django and its channel layer needs Redis,
which ADR-005 already justified for this exact phase.

Django's existing synchronous views keep working under ASGI, so the migration is a change to
how the application is *served* rather than a rewrite of what already exists.

**Alternatives considered**:

- **Polling every two seconds.** Satisfies the letter of FR-006 and needs no new
  infrastructure. Rejected on two counts: at 150 concurrent conversations it is roughly 225
  requests a second doing nothing most of the time, and a typing indicator polled at two-second
  granularity is worse than none — it tells you someone *was* typing.
- **Server-Sent Events over WSGI.** One-way push with sending over ordinary POSTs, and
  genuinely simpler than Channels. Rejected because an open SSE connection still occupies a
  WSGI worker: fifty idle agents would consume fifty workers doing nothing.
- **Channels alongside the existing WSGI server**, sockets on one, pages on the other.
  Rejected in favour of a single ASGI server: two deployments, two configurations, and a
  session cookie that has to work identically across both is more moving parts than the
  migration it avoids.

**Consequence**: the ORM is synchronous and consumers are asynchronous, so every database
touch inside a consumer goes through `database_sync_to_async`. This is the real cost of the
decision and the most likely source of subtle bugs; the services in `apps/chat/services/` stay
synchronous and ordinary, and consumers do nothing but transport.

## 2. Keeping a whisper away from the customer

**Decision**: two broadcast groups per conversation — `chat.<id>.public`, which the customer's
socket joins, and `chat.<id>.staff`, which it never does. A private note is published only to
the staff group. Group names are computed in one module, `services/groups.py`.

**Rationale**: FR-025 is the requirement in this feature whose failure is worst and least
recoverable — a private staff remark appearing in a customer's chat window, in real time,
unrecallable. Filtering at render time would work until the day someone adds a code path that
forgets. Group separation means the customer's socket is never a member of the channel the
whisper is published to, so a leak requires actively adding them to the staff group rather than
merely forgetting to filter.

This sits *on top of* the existing defences rather than replacing them: the message is still
stored with `visibility=INTERNAL`, and the existing customer-facing filter still excludes it
from the transcript and every other output. Three layers, because one of them being wrong is
survivable and all three being wrong is not.

**Alternatives considered**: one group per conversation with a `visibility` field on each
broadcast payload, filtered in the consumer before sending. Simpler, and one forgotten branch
away from disaster. Rejected: the cost of the second group is a string, and the cost of the
mistake is a customer reading what an agent was told about them.

**Consequence**: an agent's socket joins both groups; a supervisor's joins the staff group only
and its consumer rejects customer-directed sends outright (FR-022), so observation cannot
become participation by accident.

## 3. Presence and the waiting queue

**Decision**: Redis. Presence is a key per agent carrying their capacity, refreshed by a
heartbeat and given a TTL slightly longer than the heartbeat interval. The queue is a sorted
set keyed by arrival time.

**Rationale**: presence is *supposed* to be ephemeral, and this is the case where the obvious
durable choice is the wrong one. An agent whose browser closed, whose laptop slept, or whose
server restarted is not online — and a database row saying "online" will go on saying it
forever, because the process that would have corrected it is the one that died. A key with a
TTL tells the truth by default: no heartbeat, no key, not online. The failure mode is
self-correcting rather than self-perpetuating.

A sorted set gives "longest waiting first" (FR-017) as a single operation, and position
(FR-016) as a rank lookup.

**Alternatives considered**: a `Presence` table in PostgreSQL with a `last_seen` column and a
periodic sweep. Rejected because the sweep is a second moving part that exists only to
compensate for choosing durable storage for ephemeral state — and until it runs, the system
routes conversations to agents who are not there.

**Consequence**: a Redis restart empties the queue and marks everyone offline. Agents reappear
within one heartbeat. Waiting visitors are the real loss, and the system must handle it the way
FR-042 already requires — offer the request form rather than wait silently. Queue entries are
seconds to minutes old, so this is a small loss with a defined behaviour rather than an
unhandled one.

## 4. The chat client

**Decision**: htmx's WebSocket extension receiving server-rendered HTML fragments, with
Alpine.js for local state (the composer, unread badges, connection status).

**Rationale**: ADR-003 chose server-rendered Django with htmx for the MVP and explicitly left
this phase to decide whether chat justified something different. The reasons it gave have not
changed: one translation catalog serving screens and email, authorization staying on the server
because every fragment is produced by ordinary Django code, and no second build pipeline. A
socket that carries HTML keeps all three.

**Alternatives considered**: a Vue component for the chat pane. Genuinely the stronger choice
if the client needed rich local state — but chat's state is a message list, a typing flag, an
unread count and a connection status. Rejected because it would split the translation catalog
in two for one screen, which is the cost ADR-003 was most concerned about, and bilingual launch
made that cost permanent rather than temporary.

**Consequence**: the hardest part for this approach is unread counts across several
conversations, which is client state that outlives any one fragment. Alpine holds it, keyed by
conversation, updated by a small JSON control frame alongside the HTML ones. If that proves
awkward in practice, it is the one place a component framework would earn its keep, and it is
isolated enough to change without touching anything else.

## 5. Authorizing a visitor's socket

**Decision**: a signed token naming exactly one conversation, issued when the pre-chat form is
accepted and stored in the visitor's browser. The socket presents it at connect time.

**Rationale**: visitors are anonymous (FR-005) — there is no session to authenticate. The
token must therefore *be* the authorization, and it must name one conversation rather than
identify a person, because identity here is only an email address someone typed.

Channels' origin validation is applied as well, so a socket opened from another site is
refused even with a valid token.

**Alternatives considered**: a random unguessable conversation id used as a bearer value.
Rejected: a signed token can carry an expiry and be verified without a database round trip,
and an unguessable id is only unguessable until it appears in a log or a referrer.

**Consequence**: a token grants access to one conversation and nothing else, so a leaked token
exposes one conversation. It expires with the conversation, and reconnection within the grace
period (FR-032) presents the same token rather than minting a new one.

## 6. Persisting before broadcasting

**Decision**: every chat message is written to PostgreSQL first and broadcast second.

**Rationale**: FR-028 requires the transcript to be complete, and SC-003 puts that at 100%
including conversations ended by a disconnection. Broadcasting first would feel marginally
faster and would lose exactly the messages sent in the moments before a crash — which are the
ones a dispute is most likely to be about.

**Alternatives considered**: buffer in Redis and write the transcript when the conversation
ends. Faster, and it loses the entire conversation if the process dies mid-chat, which is the
opposite of what SC-003 asks for.

**Consequence**: each message costs a database write before it is seen. At this scale that is
irrelevant; it is worth stating because it is a deliberate choice of correctness over latency,
and the two-second budget in SC-002 has room for it many times over.

## 7. The Supervisor role

**Decision**: a third value on the existing role field, granted the Agent's permissions plus
observation and whispering, and explicitly denied account administration and the audit log.

**Rationale**: FR-037 settled this. Worth recording is what it does *not* change: roles remain
fixed in code and not configurable by users, so MVP FR-022's principle survives — only its
count moves.

**Consequence**: every existing permission check must be reviewed rather than assumed. A check
written as "is this user an Administrator?" stays correct; one written as "is this user *not*
an Agent?" silently grants Supervisors administrator powers. `/speckit-tasks` includes an audit
of all of them, and the existing role-enforcement sweep is extended to assert what a Supervisor
cannot do.

## Open question carried forward

**Agent capacity defaults to three** (spec assumption), and the reconnection grace period to 60
seconds with a 10-minute idle limit. These are the numbers most likely to feel wrong in
practice, and none of them can be settled by research — they need agents using the thing.
They are implemented as configuration rather than constants so that changing one is a settings
edit, not a deployment of new code.
