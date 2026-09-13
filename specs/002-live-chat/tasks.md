---
description: "Task list for the Live Chat implementation"
---

# Tasks: Live Chat

**Input**: Design documents from `specs/002-live-chat/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Test tasks are included and are **not optional**. Constitution Principle I
(Test-First) is marked NON-NEGOTIABLE. In this feature it also carries more weight than usual:
the requirements that matter most — a whisper never reaching a customer, an observer never
being visible — can only be asserted by opening two sockets at once and checking what the
*other* one did not receive.

**Numbering**: this feature numbers its own tasks from T001. References to the MVP's tasks are
written as **MVP T0xx**.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on incomplete work)
- **[Story]**: The user story this task serves (US1–US7)
- Every task names the exact file path it touches

## A note on what makes this feature different

Everything before this was asynchronous: a ticket can wait. A conversation cannot. Three
consequences shape the ordering below.

1. **The security boundary is in the wiring, not the rendering.** Group membership decides who
   can physically receive a whisper, so `services/groups.py` is foundational and is written
   once, with tests, before any consumer exists.
2. **Consumers are async and the ORM is not.** Business logic stays in ordinary synchronous
   services; consumers do transport and nothing else. A task that puts a query in a consumer is
   a task that got it wrong.
3. **Adding a role endangers existing checks.** Any permission phrased as "not an Agent" now
   grants Supervisors administrator powers, so the audit in Phase 2 is a blocking prerequisite,
   not polish.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Move the application to ASGI and stand up the machinery chat needs.

- [X] T001 Pinned `channels`, `channels-redis`, `daphne` and `uvicorn` in `requirements/base.txt`, and `pytest-asyncio` plus `websockets` in `requirements/local.txt`. Also capped `pytest<9`: installing pytest-asyncio silently upgrades pytest and breaks every `pytest-playwright` browser test for a reason unrelated to any code change
- [X] T002 Create the `apps/chat` package with `models.py`, `consumers/`, `services/`, `routing.py`, `views.py`, `urls.py`, `tests/`, and register it in `config/settings/base.py`
- [X] T003 Convert `config/asgi.py` to a `ProtocolTypeRouter`: HTTP to the Django application, WebSocket through `AllowedHostsOriginValidator` and `AuthMiddlewareStack` to the chat routing
- [X] T004 Configure `ASGI_APPLICATION` and `CHANNEL_LAYERS` (Redis) in `config/settings/base.py`, reading the Redis URL from the environment as everything else does
- [X] T005 [P] Configure an in-memory channel layer in `config/settings/test.py` so consumer tests need no Redis, and note why that is safe: the layer under test is Channels', not ours
- [X] T006 [P] Add the chat settings to `config/settings/base.py` and `.env.example` — agent capacity, reconnect grace, idle limit and warning — as configuration rather than constants (research.md, open question)
- [X] T007 [P] Vendor `htmx-ext-ws` into `static/js/` alongside htmx and Alpine, and load it in `templates/base.html`
- [X] T008 [P] Add a Redis service to `.github/workflows/ci.yml` so the channel layer and presence are exercised in CI rather than only locally
- [X] T009 [P] Document the ASGI server and the new Redis requirement in `README.md`, replacing the `runserver`-only instructions
- [X] T010 Run the whole existing suite under ASGI (`pytest` with `config/asgi.py` in place) before writing any chat code — the WSGI-to-ASGI move must be proved not to have broken the MVP, or every later failure is ambiguous

**Checkpoint**: the application serves its existing pages through uvicorn, all existing tests
pass, and a WebSocket connection is accepted and immediately closed.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The models, the group boundary, presence, the queue, and the role — everything
every story below depends on.

**⚠️ CRITICAL**: No user story work begins until this phase is complete. T017 in particular:
the Supervisor role changes the meaning of existing permission checks, and shipping a story on
top of a silently broadened check would mean auditing every screen twice.

### Tests first

- [X] T011 [P] Write `apps/chat/tests/test_groups.py` asserting the public and staff group names for a conversation are distinct, derived only from its id, and that no function in the module can return the staff name for a visitor
- [X] T012 [P] Write `apps/chat/tests/test_presence.py` asserting an agent appears online only while heartbeating, disappears when the key expires, and that capacity is reported accurately
- [X] T013 [P] Write `apps/chat/tests/test_queue.py` asserting longest-waiting-first ordering, correct position reporting, removal on leave, and scoping by department and branch
- [X] T014 [P] Write `apps/chat/tests/test_assignment.py` asserting an agent is never assigned beyond capacity, and that two simultaneous assignments cannot both claim the same slot
- [X] T015 [P] Write `apps/accounts/tests/test_supervisor_role.py` asserting a Supervisor can do everything an Agent can, plus observe and whisper, and **cannot** create accounts, change scope, or read the audit log
- [X] T016 [P] Extend `apps/accounts/tests/test_role_enforcement.py` to assert every administrator-only route refuses a Supervisor, not merely an Agent

### Implementation

- [X] T017 Audited every role check in `apps/` and `templates/`: **no changes were needed**. Every one was already written as an allowlist (`role == ADMINISTRATOR`, `role != ADMINISTRATOR`), never as "not an Agent", which is why a third role changed none of them. The audit is now permanent rather than a one-time read — `test_no_permission_check_is_phrased_as_not_an_agent` in `apps/accounts/tests/test_supervisor_role.py` scans for that shape so the next one fails at the point it is written
- [X] T018 Add `SUPERVISOR` to `User.Role` in `apps/accounts/models.py` and generate its migration, leaving every existing account on its current role
- [X] T019 Add `supervisor_required` and `can_observe` to `apps/accounts/permissions.py`, recording refused attempts as the administrator check already does
- [X] T020 Implement `Conversation` in `apps/chat/models.py` — scoped, soft-deletable, with the state machine from [data-model.md](data-model.md) and `visitor_token_hash` storing a hash, never the token
- [X] T021 Implement `Observation` in `apps/chat/models.py`, audited and **not** soft-deletable: an observation is a fact about something that happened
- [X] T022 Add `CHAT` to `Message.channel` and `Ticket.Channel` in `apps/tickets/models.py`, extending the existing model rather than introducing a second one
- [X] T023 Generate and review migrations for `chat`, `accounts` and `tickets`
- [X] T024 Register `Conversation` and `Observation` in `apps/core/audit.py`, and confirm `tests/test_audit_coverage.py` passes without being edited
- [X] T025 Implement `apps/chat/services/groups.py` — the only place public and staff group names are computed, because a boundary derived in three consumers will eventually be derived three different ways
- [X] T026 Implement `apps/chat/services/presence.py` on Redis: a per-agent key with capacity, refreshed by heartbeat, expiring on its own so a crashed agent stops being online without anything having to notice
- [X] T027 Implement `apps/chat/services/queue.py` on a Redis sorted set, scoped per department and branch
- [X] T028 Implement `apps/chat/services/assignment.py`, claiming capacity and attaching the agent in one transaction with a locked row, as MVP T072 does for taking a ticket
- [X] T029 Implement the visitor token in `apps/chat/services/tokens.py` — signed, naming one conversation, carrying an expiry, and compared against a stored hash
- [X] T030 Implement `apps/chat/routing.py` with the three socket paths from [contracts/websocket.md](contracts/websocket.md)
- [X] T031 Create `templates/chat/` and the shared fragment partials the sockets will push, with every string translated from the start
- [X] T032 [P] Seed a Supervisor account in `apps/core/management/commands/seed_demo.py` so the role is exercised in every development run

**Checkpoint**: a socket can be opened and authorized, presence and the queue behave, and no
existing permission check has been broadened by the new role.

---

## Phase 3: User Story 1 - A visitor reaches an agent and they converse (Priority: P1) 🎯 MVP

**Goal**: A visitor opens chat, reaches an available agent, and they converse in real time.

**Independent Test**: With one agent online, open chat as a visitor, send a message, and see
the agent receive it and reply — both within seconds and without a reload.

### Tests for User Story 1

- [X] T033 [P] [US1] Write `apps/chat/tests/test_visitor_consumer.py` covering the visitor socket's frames and refusals in [contracts/websocket.md](contracts/websocket.md), including a connection with no token, a bad signature, and a foreign origin
- [X] T034 [P] [US1] Write `apps/chat/tests/test_agent_consumer.py` covering the agent socket's frames, including refusal for an unauthenticated session and a conversation outside the agent's scope
- [X] T035 [P] [US1] Write `apps/chat/tests/test_message_delivery.py` asserting a message sent on one socket arrives on the other, and that it exists in the database **before** it appears on any socket (research.md #6)
- [X] T036 [P] [US1] Write `apps/chat/tests/test_typing.py` asserting a typing signal reaches the other party and stops
- [X] T037 [P] [US1] Write `apps/chat/tests/test_prechat_form.py` asserting a known email matches the existing contact, an unknown one creates a contact with no organization (MVP FR-040), and that neither creates a duplicate
- [X] T038 [P] [US1] Write `apps/chat/tests/test_arabic_chat.py` asserting Arabic message content survives the socket unchanged in both directions
- [X] T039 [P] [US1] Write `apps/chat/tests/test_rate_limit.py` asserting a flood of messages is throttled without the connection being dropped

### Implementation for User Story 1

- [X] T040 [US1] Implement the pre-chat form and `/chat/start/` in `apps/chat/views.py`, reusing `apps/customers/services/matching.py` rather than matching contacts a second way
- [X] T041 [US1] Implement `apps/chat/consumers/visitor.py` — token authorization at connect, join the public group only, never the staff group
- [X] T042 [US1] Implement `apps/chat/consumers/agent.py` — session authorization, scope check, join both groups for each held conversation
- [X] T043 [US1] Implement `apps/chat/services/messaging.py`: persist the message, then broadcast it, in that order and never the reverse
- [X] T044 [US1] Implement typing signals in `apps/chat/consumers/agent.py` and `visitor.py` as transient frames that are never persisted — a typing indicator is not part of the transcript
- [X] T045 [US1] Apply rate limiting to inbound visitor frames in `apps/chat/consumers/visitor.py`, throttling rather than disconnecting
- [X] T046 [P] [US1] Create `templates/chat/widget.html` — the visitor panel, embeddable, with `dir` and `lang` from the active language
- [X] T047 [P] [US1] Create `templates/chat/partials/message.html`, the fragment pushed for every rendered message
- [X] T048 [US1] Wire `htmx-ext-ws` into the widget and the console so fragments swap into the thread as they arrive
- [X] T049 [US1] Ensure every database call inside both consumers goes through `database_sync_to_async`, with the logic itself in `services/`
- [X] T050 [US1] Extract and compile translations for this phase into `locale/*/LC_MESSAGES/django.po`

**Checkpoint**: quickstart scenarios 1, 2 and 11 pass. Two people can hold a conversation.

---

## Phase 4: User Story 2 - An agent handles several conversations at once (Priority: P2)

**Goal**: An agent goes online, receives conversations up to capacity, and moves between them
without losing their place.

**Independent Test**: With capacity three, start four conversations; three are assigned and
reachable from one console with unread counts, and the fourth is not assigned.

### Tests for User Story 2

- [X] T051 [P] [US2] Write `apps/chat/tests/test_capacity.py` asserting a fourth conversation is not assigned to an agent already holding three
- [X] T052 [P] [US2] Write `apps/chat/tests/test_online_offline.py` asserting going offline is refused while conversations are open (FR-014), and that going offline stops new assignments
- [X] T053 [P] [US2] Write `apps/chat/tests/test_unread.py` asserting unread counts are per conversation and clear when that conversation is opened
- [X] T054 [P] [US2] Write `apps/chat/tests/test_console_context.py` asserting the console shows the customer's contact, organization and recent tickets beside each conversation
- [X] T055 [P] [US2] Write `apps/chat/tests/test_console_scope.py` asserting a conversation outside the agent's department is absent from the console and refused as not-found by its direct address

### Implementation for User Story 2

- [X] T056 [US2] Implement the online/offline frames in `apps/chat/consumers/agent.py`, refusing offline while conversations are held
- [X] T057 [US2] Implement the heartbeat frame in `apps/chat/consumers/agent.py`, refreshing the presence key's TTL in `apps/chat/services/presence.py`
- [X] T058 [US2] Implement unread tracking in `apps/chat/services/unread.py`, per agent and per conversation
- [X] T059 [US2] Implement the console view in `apps/chat/views.py`, scoped with `for_user()` like every other list in the product
- [X] T060 [P] [US2] Create `templates/chat/console.html` — the multi-conversation console
- [X] T061 [P] [US2] Create `templates/chat/partials/conversation_list.html` with unread badges
- [X] T062 [US2] Implement the Alpine state holding unread counts across fragments in `static/js/chat-console.js`, updated by a JSON control frame — the one place [ADR-008](../../docs/decisions/008-chat-client.md) named as strained
- [X] T063 [US2] Add the customer context panel to `templates/chat/console.html`, reusing the markup from `templates/tickets/partials/ticket_pane.html` rather than writing a second version
- [X] T064 [US2] Extract and compile translations for this phase into `locale/ar/LC_MESSAGES/django.po` and `locale/en/LC_MESSAGES/django.po`, then check with `tools/catalog.py status`

**Checkpoint**: quickstart scenario 3 passes. An agent can work three conversations at once.

---

## Phase 5: User Story 3 - The conversation becomes a permanent record (Priority: P3)

**Goal**: When a conversation ends, the whole transcript is on a ticket and on the customer's
timeline.

**Independent Test**: Hold a conversation, end it, then find the ticket by reference and read
the exchange in order.

### Tests for User Story 3

- [X] T065 [P] [US3] Write `apps/chat/tests/test_transcript.py` asserting every message from both parties lands on the ticket in order, attributed and timestamped
- [X] T066 [P] [US3] Write `apps/chat/tests/test_ticket_creation.py` asserting a ticket exists from the moment the conversation starts, with `origin_channel=CHAT`
- [X] T067 [P] [US3] Write `apps/chat/tests/test_reference_timing.py` asserting the visitor is given **no** reference until the conversation ends (FR-040)
- [X] T068 [P] [US3] Write `apps/chat/tests/test_attach_ticket.py` asserting attaching to an existing ticket moves the transcript there, soft-deletes the placeholder, audits both, and refuses a ticket outside the agent's scope
- [X] T069 [P] [US3] Write `apps/chat/tests/test_resolution.py` asserting an unresolved conversation leaves its ticket open, and a resolved one resolves it and can be reopened by a later customer reply
- [X] T070 [P] [US3] Write `apps/chat/tests/test_timeline_parity.py` asserting a chat ticket appears on the organization timeline identically to an emailed one

### Implementation for User Story 3

- [X] T071 [US3] Implement `apps/chat/services/transcript.py`, writing the conversation onto its ticket when it ends
- [X] T072 [US3] Create the conversation's ticket at start in `apps/chat/services/lifecycle.py`, so a transcript can never be orphaned by an unexpected ending
- [X] T073 [US3] Implement `/chat/conversations/<id>/attach/` in `apps/chat/views.py`, soft-deleting the placeholder and auditing both actions
- [X] T074 [US3] Implement ending with optional resolution, reusing `apps/tickets/services/lifecycle.py` rather than a second state machine
- [X] T075 [US3] Show the reference to the visitor in the `ended` frame emitted by `apps/chat/consumers/visitor.py`, and only there (FR-040)
- [X] T076 [US3] Extract and compile translations for this phase into `locale/ar/LC_MESSAGES/django.po` and `locale/en/LC_MESSAGES/django.po`, then check with `tools/catalog.py status`

**Checkpoint**: quickstart scenarios 4 and 5 pass. Chat is part of the CRM, not a widget.

---

## Phase 6: User Story 4 - A supervisor watches a live conversation (Priority: P4)

**Goal**: A supervisor reads a live conversation with full customer context, invisibly to the
customer and without interrupting the agent.

**Independent Test**: With a conversation in progress, open it as a supervisor and see new
messages appear as they are sent, while the visitor's window shows no change of any kind.

### Tests for User Story 4

- [X] T077 [P] [US4] Write `apps/chat/tests/test_supervisor_consumer.py` covering the supervisor socket's frames and refusals in [contracts/websocket.md](contracts/websocket.md)
- [X] T078 [P] [US4] Write `apps/chat/tests/test_observation_invisible.py` asserting that a supervisor connecting, observing and disconnecting produces **no frame of any kind** on the visitor's socket — not merely no message (FR-021)
- [X] T079 [P] [US4] Write `apps/chat/tests/test_observer_cannot_speak.py` asserting a customer-directed frame from a supervisor is rejected outright and appears on no socket (FR-022)
- [X] T080 [P] [US4] Write `apps/chat/tests/test_observation_scope.py` asserting a conversation outside the supervisor's department is refused as not-found, never as forbidden (FR-043, MVP FR-024)
- [X] T081 [P] [US4] Write `apps/chat/tests/test_observation_record.py` asserting an Observation row is opened on connect and closed on disconnect, naming who watched what and when (FR-023)
- [X] T082 [P] [US4] Write `apps/chat/tests/test_agent_cannot_observe.py` asserting the Agent role is refused the supervisor socket and every `/chat/supervise/` path

### Implementation for User Story 4

- [X] T083 [US4] Implement `apps/chat/consumers/supervisor.py` — joins the **staff group only**, so an observer is not a participant and cannot become one by accident
- [X] T084 [US4] Reject customer-directed frames explicitly in `apps/chat/consumers/supervisor.py`, rather than relying on the absence of a handler — an unhandled frame is silence, a rejected one is a decision
- [X] T085 [US4] Open and close the `Observation` record on connect and disconnect in `apps/chat/consumers/supervisor.py`
- [X] T086 [US4] Implement `/chat/supervise/` and `/chat/supervise/<id>/` in `apps/chat/views.py`, scoped and supervisor-only
- [X] T087 [P] [US4] Create `templates/chat/supervise.html` — the live conversations list and the observation view, reusing the customer context panel
- [X] T088 [US4] Extract and compile translations for this phase into `locale/ar/LC_MESSAGES/django.po` and `locale/en/LC_MESSAGES/django.po`, then check with `tools/catalog.py status`

**Checkpoint**: quickstart scenarios 6 and 8 pass. A supervisor can watch without being seen
and without being able to speak.

---

## Phase 7: User Story 5 - A supervisor coaches the agent privately (Priority: P5)

**Goal**: A private note reaches the agent during a live conversation and reaches the customer
under no circumstances.

**Independent Test**: Send a whisper. The agent sees it, the customer's window shows nothing at
all, and the transcript given to the customer never contains it.

**This is the phase the MVP prepared for.** The visibility boundary was built into the MVP
ahead of time specifically so that this feature would land on tested ground rather than
introduce the boundary and its first user at the same time.

### Tests for User Story 5

- [X] T089 [P] [US5] Write `tests/test_whisper_isolation.py` as the cross-cutting invariant: open a visitor socket and a staff socket on one conversation, send a whisper, and assert the visitor's socket receives **nothing at all**
- [X] T090 [P] [US5] Extend `tests/test_internal_visibility.py` so its customer-facing sweep covers chat transcripts alongside the email and intake templates it already checks
- [X] T091 [P] [US5] Write `apps/chat/tests/test_whisper_storage.py` asserting a whisper is stored as a Message with `visibility=INTERNAL` and `channel=CHAT`, reusing the MVP's model
- [X] T092 [P] [US5] Write `apps/chat/tests/test_whisper_in_transcript.py` asserting the whisper is on the ticket for staff and absent from every customer-facing output (FR-025)
- [X] T093 [P] [US5] Write `apps/chat/tests/test_whisper_distinct.py` asserting the agent's view marks a private note by wording as well as colour, as the ticket thread already does (FR-026)
- [X] T094 [P] [US5] Write `apps/chat/tests/test_whisper_cannot_be_misaddressed.py` asserting the agent's reply composer and the supervisor's whisper composer post to different destinations, so neither can become the other by a mode being wrong (FR-027)
- [X] T095 [P] [US5] Write `apps/chat/tests/test_whisper_edge_cases.py` covering a whisper to a disconnected agent, and a whisper sent as the conversation ends

### Implementation for User Story 5

- [X] T096 [US5] Implement the `whisper` frame in `apps/chat/consumers/supervisor.py`, publishing **only** to the staff group named by `apps/chat/services/groups.py`
- [X] T097 [US5] Persist the whisper through `apps/chat/services/messaging.py` with `visibility=INTERNAL`, before broadcasting, as every other message is
- [X] T098 [P] [US5] Create `templates/chat/partials/whisper.html`, marked as the ticket thread's internal note is — wash, edge, icon, and the restriction written out
- [X] T099 [US5] Hold an undelivered whisper in `apps/chat/services/messaging.py` for an agent who reconnects within the grace period, and do not deliver it to whoever takes the conversation over instead
- [X] T100 [US5] Extract and compile translations for this phase into `locale/ar/LC_MESSAGES/django.po` and `locale/en/LC_MESSAGES/django.po`, then check with `tools/catalog.py status`

**Checkpoint**: quickstart scenario 7 passes. The feature's most damaging failure is tested
from both ends.

---

## Phase 8: User Story 6 - Everyone is busy, or the desk is closed (Priority: P6)

**Goal**: A visitor arriving when all agents are busy waits with a moving position; a visitor
arriving when nobody is online is not offered chat at all.

**Independent Test**: With no agents online, confirm chat is not offered and the request form
is. With an agent online at capacity, confirm a visitor queues with a position that updates.

### Tests for User Story 6

- [X] T101 [P] [US6] Write `apps/chat/tests/test_availability.py` asserting `/chat/availability/` answers "no" when no agent is online and "yes" when one is, without querying conversation history
- [X] T102 [P] [US6] Write `apps/chat/tests/test_queueing.py` asserting a visitor queues when all agents are at capacity, is shown a position, and that the position updates as the queue moves
- [X] T103 [P] [US6] Write `apps/chat/tests/test_queue_fairness.py` asserting the longest-waiting visitor is connected first (FR-017)
- [X] T104 [P] [US6] Write `apps/chat/tests/test_desk_closed.py` asserting chat is not offered at all with nobody online, and the request form is presented instead (FR-039)
- [X] T105 [P] [US6] Write `apps/chat/tests/test_last_agent_leaves.py` asserting a waiting visitor is moved to the request form immediately when the last online agent goes offline, with their typed text carried over (FR-042)
- [X] T106 [P] [US6] Write `apps/chat/tests/test_leave_queue.py` asserting a visitor who closes the panel is removed, so no agent is assigned a conversation nobody is waiting on (FR-019)

### Implementation for User Story 6

- [X] T107 [US6] Implement `/chat/availability/` in `apps/chat/views.py` as a cheap presence lookup, since the public site calls it on every page load
- [X] T108 [US6] Implement queue placement, position frames, and connection of the longest-waiting visitor in `apps/chat/services/queue.py`
- [X] T109 [US6] Implement the last-agent-offline handler in `apps/chat/services/queue.py`, moving everyone waiting to the request form with their draft (FR-042)
- [X] T110 [US6] Hide the chat launcher in `templates/chat/widget.html` when availability says no, and compile translations into `locale/*/LC_MESSAGES/django.po`

**Checkpoint**: quickstart scenario 9 passes. Nobody waits for a desk that has closed.

---

## Phase 9: User Story 7 - A connection drops (Priority: P7)

**Goal**: A network failure loses neither the conversation nor the other party's attention.

**Independent Test**: Interrupt the visitor's connection mid-conversation and restore it; the
conversation resumes with history intact and nothing sent in between is lost.

### Tests for User Story 7

- [X] T111 [P] [US7] Write `apps/chat/tests/test_reconnect.py` asserting a visitor reconnecting within the grace period resumes the same conversation with full history, presenting the same token
- [X] T112 [P] [US7] Write `apps/chat/tests/test_visitor_gone.py` asserting a visitor who does not return ends the conversation, saves the transcript, and tells the agent why rather than leaving them waiting (FR-033)
- [X] T113 [P] [US7] Write `apps/chat/tests/test_agent_gone.py` asserting an agent who does not return returns the conversation to the queue with its history, and the visitor is told they are being reconnected (FR-034)
- [X] T114 [P] [US7] Write `apps/chat/tests/test_missed_messages.py` asserting a message sent while a party was briefly disconnected is delivered on reconnection (FR-035)
- [X] T115 [P] [US7] Write `apps/chat/tests/test_idle_timeout.py` asserting both parties are warned before an idle conversation closes, not after (FR-036)
- [X] T116 [P] [US7] Write `apps/chat/tests/test_deactivated_agent.py` asserting an agent deactivated mid-conversation has their sockets closed and their conversation requeued (MVP FR-026)

### Implementation for User Story 7

- [X] T117 [US7] Implement the reconnection window in `apps/chat/services/lifecycle.py`, keyed on the same visitor token rather than a new one
- [X] T118 [US7] Implement requeueing in `apps/chat/services/lifecycle.py` for a conversation whose agent is lost, preserving its history and its ticket
- [X] T119 [US7] Implement replay of missed messages in `apps/chat/services/messaging.py`, read from the database rather than an in-memory buffer — the buffer is what a crash loses
- [X] T120 [US7] Implement the idle sweep in `apps/chat/tasks.py` on Celery Beat — warn, then close — and extract and compile translations for this phase

**Checkpoint**: quickstart scenarios 10 and 12 pass. A bad network is an inconvenience, not a
data loss.

---

## Phase 10: Polish & Cross-Cutting Concerns

- [ ] T121 [P] Write `tests/e2e/test_two_party_chat.py` driving **two real browsers at once** through a whole conversation — the only test that exercises what two people actually experience
- [ ] T122 [P] Extend `tests/e2e/test_rtl_layout.py` to the chat widget and console, measuring rendered geometry as it already does for the queue and ticket detail
- [ ] T123 [P] Write `tests/e2e/test_whisper_visual.py` asserting the private note is distinguishable in a real browser under a greyscale filter, as `test_internal_note_visual.py` does for the ticket thread
- [ ] T124 [P] Extend `tests/test_scope_isolation.py` to cover the chat routes, so the 404-not-403 sweep includes them automatically
- [ ] T125 [P] Add query-count budgets for the console and the conversation view in `tests/test_query_budget.py`, asserting queries do not grow with the number of conversations held
- [ ] T126 [P] Load-test 150 concurrent conversations against the assumed 50 agents, recording the result in `docs/operations.md` rather than asserting a timing in the suite
- [ ] T127 [P] Verify the widget on a phone in `tests/e2e/test_mobile_layout.py` — chat is the most likely of all these screens to be used on one
- [ ] T128 [P] Accessibility pass over the widget and console in `tests/e2e/test_accessibility.py`: a live region so a screen reader announces arriving messages, which no other screen in this product needs
- [ ] T129 [P] Complete both translation catalogs and confirm `tools/catalog.py status` reports nothing missing and nothing fuzzy
- [ ] T130 Review every consumer for database access outside `database_sync_to_async`, and for business logic that belongs in `services/`
- [ ] T131 Document the chat operator's view in `docs/agent-guide.md` — going online, capacity, and what a private note is — in Arabic and English
- [ ] T132 Document supervision in `docs/agent-guide.md`: what a supervisor can see, what is recorded when they watch, and that agents know observation is logged
- [ ] T133 Update `docs/production-readiness.md`: Redis is now required for the product to function at all, not only for background jobs
- [ ] T134 Run all twelve validation scenarios in [quickstart.md](quickstart.md) in both languages

---

## Dependencies

### Phase order

```text
Phase 1 Setup (ASGI)
   └─▶ Phase 2 Foundational  ◀── blocks everything; T017 blocks every story
          ├─▶ Phase 3 US1 (P1)  🎯 the conversation itself
          │      ├─▶ Phase 4 US2 (P2)   needs a conversation to have several of
          │      ├─▶ Phase 5 US3 (P3)   needs a conversation to transcribe
          │      └─▶ Phase 6 US4 (P4)   needs a conversation to observe
          │             └─▶ Phase 7 US5 (P5)   whisper needs the staff group joined
          ├─▶ Phase 8 US6 (P6)   needs presence and the queue, not a conversation
          └─▶ Phase 9 US7 (P7)   needs sockets to interrupt
                 └─▶ Phase 10 Polish
```

### Hard ordering constraints

1. **T017 before every user story.** The Supervisor role broadens any check phrased as "not an
   Agent". Building on top of a silently broadened check means auditing every screen twice.
2. **T025 before any consumer.** The public/staff group split is the security boundary; a
   consumer written before it exists will compute group names itself, and then there are two
   definitions of the boundary.
3. **T018 before T023.** The role value must exist before the migration that references it.
4. **US1 before US2, US3, US4.** Each needs a conversation to exist first.
5. **US4 before US5.** A whisper is published to the staff group, which the supervisor consumer
   joins.
6. **T010 before any chat code.** The WSGI-to-ASGI move must be proved not to have broken the
   MVP, or every later failure is ambiguous.

### Story independence

US1 delivers value alone: two people can talk and it is recorded. US6 is independent of a
conversation existing — it is about their absence — and could be built in parallel with US2 and
US3 by a second person.

## Parallel execution examples

**Phase 2 tests**: T011 to T016 are six independent files, all writable before any
implementation.

**Phase 3**: the seven test tasks T033 to T039 run in parallel; then T041 and T042 are separate
consumers; T046 and T047 are separate templates.

**Phase 7**: all seven whisper tests T089 to T095 are independent, and worth writing together
because they define one boundary from several directions.

**Phase 10**: T121 to T129 are all independent.

## Implementation strategy

**Minimum demonstrable increment**: Phases 1 to 3. Two people can hold a real conversation that
is recorded. Worth showing to agents before building the rest, because the feel of it — latency,
typing indicators, how a conversation ends — is the part written requirements capture worst.

**First genuinely useful release**: add Phases 4, 5 and 8. An agent can work several
conversations, every one lands on a ticket, and nobody waits for a closed desk. This is a
shippable chat product without supervision.

**Complete feature**: Phases 6, 7 and 9, then 10. Supervision is what the MVP's visibility
boundary was built for, and Phase 9 is what makes the whole thing trustworthy on a real network.

**Task total**: 134. Setup 10, Foundational 22, US1 18, US2 14, US3 12, US4 12, US5 12, US6 10,
US7 10, Polish 14.
