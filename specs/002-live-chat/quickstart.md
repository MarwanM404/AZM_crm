# Quickstart & Validation: Live Chat

**Date**: 2026-09-12 | **Plan**: [plan.md](plan.md)

How to run live chat locally and prove it works. Each scenario maps onto a user story in
[spec.md](spec.md), so a passing run is evidence against the specification rather than a smoke
test.

## Prerequisites

Everything the MVP needs, plus:

- **Redis** — now required rather than optional. It carries the channel layer, presence and
  the queue. Without it there is no chat at all, where previously it only affected background
  jobs.

## Setup

```bash
uv sync                       # picks up channels, channels-redis, uvicorn
python manage.py migrate
python manage.py compilemessages
python manage.py seed_demo    # now also seeds a Supervisor account
```

## Running

The development server changes. `runserver` still works — Django serves ASGI through it — but
it is worth running the real server at least once, because it is what production uses:

```bash
uvicorn config.asgi:application --reload    # HTTP and WebSocket, one process
celery -A config worker -l info
celery -A config beat -l info
```

## Test suite

```bash
pytest                         # everything
pytest -m "not e2e"            # skip the browser tests
pytest apps/chat/              # this feature only
```

Three test layers, because the interesting failures live at different levels:

| Layer | Tool | What only it can catch |
|---|---|---|
| Services | plain pytest | Assignment respecting capacity; queue ordering; presence expiry |
| Consumers | `WebsocketCommunicator` | What a socket receives **and what another socket does not** |
| Two browsers | Playwright | A real conversation between two people, in two languages |

The cross-cutting invariant is `tests/test_whisper_isolation.py`, and it is the one that must
never be skipped: it opens a visitor socket and a staff socket on the same conversation, sends
a whisper, and asserts the visitor's socket receives **nothing at all** — not merely nothing
internal.

## Validation scenarios

### 1. A visitor reaches an agent (User Story 1)
Sign in as an agent, go online. In another browser, open `/chat/widget/`, submit the pre-chat
form. **Expect**: the agent is offered the conversation, both see it open, and a message typed
in one appears in the other within two seconds without a reload.

### 2. Typing indicators (FR-007)
Type in one window without sending. **Expect**: the other shows that a reply is being composed,
and it stops when typing stops.

### 3. Three at once (User Story 2)
With capacity three, start four conversations from four visitor sessions. **Expect**: three are
assigned; the fourth queues with a position. The console shows unread counts for whichever
conversation the agent is not looking at.

### 4. The transcript lands on a ticket (User Story 3)
End a conversation. **Expect**: a ticket exists with the whole exchange in order, each message
attributed and timestamped, the ticket visible on the customer's organization timeline, and the
reference shown to the visitor only now — not at the start.

### 5. Attaching to an existing ticket (FR-038, FR-041)
Mid-conversation, attach it to an older ticket. **Expect**: the transcript lands on that ticket,
the placeholder is soft-deleted, both actions appear in the audit log, and the reference the
visitor finally receives is the older ticket's.

### 6. A supervisor watches (User Story 4)
As a Supervisor, open the live conversation. **Expect**: messages appear as they are sent; the
visitor's window shows no change of any kind; an Observation row records who watched what.

### 7. The whisper (User Story 5) — the one that matters
Send a private note. **Expect**: the agent sees it, marked as private by wording as well as
colour. The visitor's window shows **nothing** — no message, no notification, no flicker. End
the conversation and read the transcript: the note is there for staff and absent from anything
customer-facing.

### 8. A supervisor cannot talk to the customer (FR-022)
From the supervisor view, attempt to send a customer-directed message. **Expect**: refused. If
this ever succeeds, observation has become participation and the feature is unsafe.

### 9. The desk is closed (User Story 6)
Set every agent offline. **Expect**: the public site does not offer chat at all and shows the
request form. Then queue a visitor and take the last agent offline. **Expect**: the waiting
visitor is moved to the form immediately, with their typed text carried over.

### 10. A connection drops (User Story 7)
Kill the visitor's network for 30 seconds and restore it. **Expect**: the same conversation
resumes with full history and nothing sent in between is lost. Repeat past the grace period:
the conversation ends, the transcript saves, and the agent is told why.

### 11. Arabic, end to end (FR-010, SC-009)
Run scenario 1 entirely in Arabic. **Expect**: both the widget and the console read
right-to-left, every label is Arabic, Arabic messages survive unchanged, and the ticket
reference stays left-to-right inside Arabic text.

### 12. An agent is deactivated mid-conversation (edge case, MVP FR-026)
Deactivate an agent holding a live conversation. **Expect**: their sockets close, and the
conversation returns to the queue rather than stranding on a disabled account.

## Definition of done for any task in this feature

Everything in the MVP's list, plus:

1. A consumer test asserts what the **other** socket received, not only what this one did.
2. Anything touching the whisper path has a test asserting the visitor's socket is silent.
3. Any new permission check names the roles it allows, rather than excluding Agent — a check
   phrased as "not an Agent" now grants Supervisors administrator powers.
4. Any database access inside a consumer goes through `database_sync_to_async`.
