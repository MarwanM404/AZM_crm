# Production readiness

**Status**: not met. **The system must not hold a real customer's record until it is.**

The MVP is built and tested. What remains is not code — it is the small number of things that
only become possible once there is a production environment, and that protect other people's
data rather than the developer's convenience.

These were removed from the feature task list on 2026-09-12 because none of them can be done
on a developer's machine. They live here so that deferring them stays a decision someone made
rather than something that was quietly forgotten.

---

## Before real customer data goes in

### 1. Encryption of personal data at rest
*Was T144. Required by the constitution's Security & Access Control principle.*

The system stores names, email addresses, phone numbers and the content of people's support
requests. On an unencrypted disk, anyone with the machine has all of it.

This is a property of the host, not of the application: an encrypted volume, or a managed
database with encryption enabled. **Record which mechanism is in use in `docs/operations.md`**,
because "we think it's encrypted" is not an answer anyone can act on later.

### 2. A backup and restore drill
*Was T146.*

Not a backup schedule — a **restore**, performed once, end to end, by someone who then writes
down what they did. A backup nobody has restored from is a belief, not a backup, and the day
you find out is the worst possible day.

Record the procedure and how long a restore actually took.

### 3. Outbound and inbound email
*The remaining half of T145. See [email-setup.md](email-setup.md), written to hand to IT.*

Until a mail domain and route exist, an agent can write a reply and the system records it on
the ticket, but **nothing is delivered to the customer**. This is the one gap between the
current build and the specification's own definition of done.

### 4. Run the eleven validation scenarios
*Was T148. See [quickstart.md](../specs/001-mvp-ticket-desk/quickstart.md).*

All eleven can be run today except scenario 5, which needs a real mailbox. Run them in both
languages against the production environment before the first real customer request, not
against a developer machine.

### 5. An ASGI server and a reachable Redis
*Added 2026-09-12 with [ADR-007](decisions/007-realtime-transport.md).*

Live chat moved the application from WSGI to ASGI. The deployment target must therefore run an
ASGI process — uvicorn, or gunicorn with `UvicornWorker` — and hold long-lived connections
through whatever proxy sits in front of it. A proxy that closes idle connections after 30
seconds will disconnect every quiet conversation.

Redis is no longer merely useful. Without it there is no chat: it carries the channel layer,
agent presence, the waiting queue and connection liveness. A Redis outage now degrades a
customer-facing feature rather than delaying a background job.

**Two things about that changed again in phase 9, and both need an operator to know them.**

Celery *Beat* is now load-bearing, not only a worker. Three periodic sweeps uphold three
requirements — nobody waits for a closed desk (FR-042), a party who went silent is acted on
(FR-033, FR-034), and an idle conversation is warned before it closes (FR-036). With Beat
stopped, nothing fails: the guarantees simply stop holding, quietly.

And **Beat must be stopped before Redis is**. A liveness key that cannot be read is
indistinguishable from one that expired, so a running sweep against an unreachable Redis would
end every live conversation as "the visitor disconnected". The restart procedure is in
[operations.md](operations.md), together with the load measurements and the tunables.

---

## Not blocking, but unverified by a person

The automated suite covers a great deal, but three things need a human and have not had one:

- **A screen-reader pass** through the agent flow in both languages. Arabic especially — see
  [accessibility-review.md](accessibility-review.md) for what automation can and cannot decide.
- **Colour-contrast measurement** against WCAG AA. The palette was chosen to be legible but
  has not been measured; the status and priority pills are the likeliest failures.
- **SC-008**: three agents completing the full flow unaided, with nothing but
  [agent-guide.md](agent-guide.md).

---

## What is already safe

For balance, these are done and verified rather than pending:

- Secrets are read from the environment and never committed; production settings fail loudly
  on a missing one rather than falling back to something usable.
- Passwords are excluded from the audit log, which is immutable by design.
- Every query is scoped by department and branch; out-of-scope records return 404, not 403.
- Internal staff notes cannot reach a customer through any output path, attachments included.
- Uploaded files are served as opaque downloads and are reachable only through a scope-checked
  view.
