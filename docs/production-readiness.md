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

### 6. One-click sign-in is off, and cannot be turned on
*Added 2026-09-13 with [spec 003](../specs/003-fix-admin-and-signin/spec.md).*

The sign-in screen can offer a button that signs somebody in as an agent, a supervisor or an
administrator without a password. It exists for development and it must never reach a
deployment, so the gate is designed around that failure rather than around the feature.

`QUICK_SIGN_IN_ENABLED` defaults to `False`, and `config/settings/production.py` assigns it
the literal `False` — **not** from the environment. That is the point: a value read from the
environment can be off wherever it is checked and on in production, and one mistyped
deployment variable would put one-click administrator access on a public page.

Two tests hold it, in `apps/accounts/tests/test_quick_sign_in.py`:

- `test_production_sets_it_off_literally` reads the production module's source and fails if
  the assignment is anything but the literal. Rewriting it to read the environment fails this.
- `test_production_cannot_be_talked_into_enabling_it` imports the module with the environment
  variable set to `1`, `true`, `True`, `yes` and `on`, and fails if the value moves.

A third, `test_the_route_refuses_when_disabled`, calls the route directly with no control
rendered anywhere. That is the one to keep: hiding a button is presentation, and a route that
still works when its button is hidden is a route somebody will find.

Nothing to verify before release beyond confirming those tests run, because there is nothing
an operator can configure here. If the sign-in screen of a deployment ever shows a
"Development sign-in" section, the deployment is not using the production settings module.

### 7. Static files are served without cache busting
*Found 2026-09-14, while fixing the chat console's presence state.*

Scripts and stylesheets are referenced by a plain path — `/static/js/chat-console.js` — with
no version in the name or the query string, and no `STORAGES` / `STATICFILES_STORAGE` setting
configured. Browsers and any CDN in front of the application will therefore keep serving the
previous file after a deployment, for as long as their cache says it is fresh.

This is not theoretical. The console's presence bug was fixed, the server was restarted, and
the browser went on running the old JavaScript through a full reload — the fix looked like it
had not worked. A returning user after a deployment is in exactly that position, with no
reason to suspect a stale file.

The usual remedy is Django's `ManifestStaticFilesStorage`, which renames each file with a
hash of its contents so a changed file has a new URL. It requires `collectstatic` as a
deployment step, which this deployment does not currently have — which is why it is recorded
here as a decision to take rather than applied quietly as part of a bug fix.

Until then: a deployment that changes a script or a stylesheet needs users told to reload, and
"it did not work" reports after a release should be checked against a hard refresh first.

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
