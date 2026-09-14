---

description: "Task list for the customer portal"
---

# Tasks: The customer portal

**Input**: Design documents from `/specs/004-customer-portal/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Mandatory. Constitution I makes test-first non-negotiable, and FR-038 requires every
check this feature adds to be demonstrated failing against the defect it guards. Several phases
therefore end with a task that breaks something deliberately.

**Organization**: Grouped by user story. Two groupings differ from the template on purpose, and
[plan.md](plan.md) says why:

- **User Story 6 is in the foundational phase, not at the end.** "A customer is not staff" is a
  property of the account model and the session, so it is built with them. Left until last it
  becomes a sweep over finished work, and a sweep is what you do when you no longer trust the
  design.
- **The internal-message sweep is extended in setup**, before the first portal template exists.
  Adding templates under a check that does not cover them is how a customer-facing screen ships
  unswept — and this project has already watched a catalog check report clean on a file it was
  not reading.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: The user story this serves (US1–US6)

---

## Phase 1: Setup

**Purpose**: The application skeleton, and the guards that must exist before anything they
guard does.

- [ ] T001 Create the `apps/portal/` application with `models.py`, `views.py`, `urls.py`, `services/` and `tests/`, and register it in `config/settings/base.py`
- [ ] T002 Route `/portal/` in `config/urls.py`, and create `templates/portal/` with a base template extending the product's existing chrome
- [ ] T003 Extend `CUSTOMER_FACING_DIRS` in `tests/test_internal_visibility.py` with `templates/portal/`, so every portal template joins the sweep by directory rather than by being listed
- [ ] T004 Demonstrate T003 works: add a template under `templates/portal/` that renders a ticket's staff view, confirm the sweep fails and names it, then remove it
- [ ] T005 [P] Add the portal's settings to `config/settings/base.py`: rate limits per address and per source for registration, sign-in, reset, confirmation, reply and new request; lockout threshold and period; confirmation and reset link lifetimes

**Checkpoint**: a portal template cannot ship without being swept for internal messages.

---

## Phase 2: Foundational — and User Story 6 (Priority: P1)

**⚠️ BLOCKS EVERY OTHER STORY.** Nothing can read or write a customer's data before there is a
customer, and nothing should be able to read staff data ever.

**Goal**: A customer account exists, has its own session, and reaches the portal and nothing
else.

**Independent Test**: Sign in as a customer and attempt every staff route, including by typing
the address directly. Then force a department onto the account and attempt them again.

**On the labels in this phase**: tasks carrying **[US6]** are the refusal itself — they are that
story and nothing else. The unlabelled tasks are the account, the session and the middleware,
which every story needs, so they follow the template's foundational rule and take no label. The
phase is a hybrid because the refusal and the thing refused are the same object.

### Tests for the foundation and User Story 6

- [ ] T006 [P] [US6] Write `apps/portal/tests/test_account_model.py` asserting `CustomerAccount` has no role, department or branch field — not empty ones, absent ones — and that nothing in `apps/portal/` assigns any
- [ ] T007 [P] [US6] Write `apps/portal/tests/test_staff_routes_refuse_customers.py` enumerating every staff route from the URL configuration and asserting a customer session reaches none of them, so a route added later is covered on the day it is added (FR-029)
- [ ] T008 [P] [US6] Extend `apps/portal/tests/test_staff_routes_refuse_customers.py` asserting those refusals still hold when a department is forced onto the customer account by any means — the refusal must rest on being a customer, not on having no scope (FR-028). **This is the test the architecture exists for**
- [ ] T009 [P] [US6] Write `apps/portal/tests/test_staff_are_not_customers.py` asserting a staff session reaches no portal route (FR-030)
- [ ] T010 [P] [US6] Extend `apps/portal/tests/test_staff_routes_refuse_customers.py` asserting a customer cannot reach the administrator self-service scope recovery added by spec 003 — an account without a scope is not necessarily an administrator who needs one
- [ ] T011 [P] [US6] Write `apps/portal/tests/test_account_deactivation.py` asserting a deactivated customer's next request is refused (FR-031)
- [ ] T012 [P] [US6] Write `apps/portal/tests/test_one_address_one_kind.py` asserting an address cannot be both a staff account and a customer account (FR-032)
- [ ] T013 [P] Write `apps/portal/tests/test_token_model.py` asserting a link value cannot be recovered from storage, that `used_at` and `expires_at` are enforced, and that a confirmation link cannot be used as a reset

### Implementation

- [ ] T014 Implement `CustomerAccount` in `apps/portal/models.py` — email, password, `email_confirmed_at`, language, `is_active`, timestamps. No role, no department, no branch
- [ ] T015 Implement `CustomerToken` in `apps/portal/models.py` — account, purpose, `expires_at`, `used_at`, with the value stored so the table is not a list of live credentials
- [ ] T016 Create the migration and confirm it adds two tables and alters no column on `Ticket`, `Message`, `Contact` or `User`
- [ ] T017 Implement the customer session in `apps/portal/auth.py` — sign in, sign out, and a session key distinct from the staff session
- [ ] T018 Implement `apps/portal/middleware.py` putting `request.customer` on the request and refusing a staff session at the portal, and register it in `config/settings/base.py`
- [ ] T019 Implement the portal's access decorator in `apps/portal/auth.py`, requiring a customer whose address is confirmed, and refusing anything else
- [ ] T020 Register `CustomerAccount` and `CustomerToken` for auditing in `apps/core/audit.py`, excluding the password and the link value — the audit log is immutable, so anything that reaches it stays (this product has excluded a password hash once already)
- [ ] T021 Demonstrate the refusals fail when broken: make the portal's decorator accept any authenticated request, confirm T007 and T008 fail; restore

**Checkpoint**: a customer account exists and reaches nothing it should not. Every later phase adds screens behind this.

---

## Phase 3: User Story 1 - Signing up and proving who you are (Priority: P1) 🎯 MVP

**Goal**: Register with an address and a password, confirm the address, sign in.

**Independent Test**: Register, confirm, sign in. Then attempt each step out of order.

### Tests for User Story 1

- [ ] T022 [P] [US1] Write `apps/portal/tests/test_registration.py` asserting an account is created unusable and a confirmation is sent to the address claimed, and only there
- [ ] T023 [P] [US1] Extend `test_registration.py` asserting an unconfirmed account reaches no portal route at all (FR-002)
- [ ] T024 [P] [US1] Extend `test_registration.py` asserting the response for an address that already has an account is **byte-identical** to a first registration, and that no second account is created (FR-007)
- [ ] T025 [P] [US1] Extend `test_registration.py` asserting the owner of an already-registered address is told an attempt was made (FR-008)
- [ ] T026 [P] [US1] Extend `test_registration.py` asserting an address with existing tickets discloses nothing about them before confirmation
- [ ] T027 [P] [US1] Extend `test_registration.py` asserting an address with no history at all can register — a customer exists before their first ticket does (FR-009)
- [ ] T028 [P] [US1] Write `apps/portal/tests/test_confirmation.py` asserting a link works once, stops working after its configured lifetime, and that a new one can be requested
- [ ] T029 [P] [US1] Write `apps/portal/tests/test_password_policy.py` asserting a password below the configured strength and a known-common password are both refused with a reason (FR-005)
- [ ] T030 [P] [US1] Write `apps/portal/tests/test_sign_in.py` asserting an unconfirmed account is told the address is unconfirmed rather than that the password is wrong
- [ ] T031 [P] [US1] Write `apps/portal/tests/test_rate_limits.py` asserting registration, sign-in and confirmation each refuse beyond their configured limit and say when to try again — with the rate limiter's cache cleared between tests, which this project has been caught by before

### Implementation

- [ ] T032 [US1] Implement registration in `apps/portal/services/registration.py`, including the identical-response rule and the notice to an already-registered address
- [ ] T033 [US1] Implement confirmation in `apps/portal/services/registration.py` — single use, expiring, and the only thing that makes an account usable
- [ ] T034 [US1] Implement the password policy in `apps/portal/services/passwords.py`
- [ ] T035 [US1] Implement the registration, confirmation and sign-in views in `apps/portal/views.py` and route them in `apps/portal/urls.py`
- [ ] T036 [US1] Apply rate limits to all three, per address and per source
- [ ] T037 [P] [US1] Create `templates/portal/register.html`, `sign_in.html` and `confirm.html`, carrying the product's chrome and the language switch that works without a session
- [ ] T038 [P] [US1] Create the confirmation and already-registered emails in `templates/portal/email/`, in both languages, composed in the recipient's language rather than whatever is active when they are queued
- [ ] T039 [US1] Add the five session-less routes to `LOGIN_EXEMPT_URL_NAMES` with the written justification per entry that `apps/accounts/tests/test_anonymous_access.py` demands
- [ ] T040 [US1] Extract and translate this phase's strings into both domains, then check with `tools/catalog.py status` and `tools/catalog.py placeholders`
- [ ] T041 [US1] Demonstrate the disclosure rule fails when broken: make registration answer differently for a known address, confirm T024 fails; restore

**Checkpoint**: somebody can create an account and sign in. Nothing yet to see.

---

## Phase 4: User Story 2 - Seeing your own requests (Priority: P1)

**Goal**: A signed-in customer sees their requests and opens one.

**Independent Test**: Sign in as a customer with tickets; confirm theirs appear and another's is not found.

### Tests for User Story 2

- [ ] T042 [P] [US2] Write `apps/portal/tests/test_request_list.py` asserting the list shows the requests raised from the confirmed address, with reference, subject, status and both dates
- [ ] T043 [P] [US2] Extend `test_request_list.py` asserting a customer whose address matches no contact sees an empty list and an invitation, not an error (research.md §2)
- [ ] T044 [P] [US2] Extend `test_request_list.py` asserting a colleague's requests at the same organization are absent (FR-018)
- [ ] T045 [P] [US2] Extend `test_request_list.py` asserting an address recorded on two contacts sees both histories
- [ ] T046 [P] [US2] Write `apps/portal/tests/test_request_detail.py` asserting the customer-facing conversation appears in order
- [ ] T047 [P] [US2] Extend `test_request_detail.py` asserting an internal note is absent from the page and from its source (FR-016)
- [ ] T048 [P] [US2] Extend `test_request_detail.py` asserting another customer's request is refused **identically** to a reference that does not exist — same status, same body (FR-017)
- [ ] T049 [P] [US2] Extend `test_request_detail.py` asserting resolved and closed requests stay readable (FR-019)
- [ ] T050 [P] [US2] Write `tests/test_query_budget.py` coverage asserting the portal list does not issue a query per request

### Implementation

- [ ] T051 [US2] Implement reading in `apps/portal/services/tickets.py`, matching contacts by confirmed address at read time and reading messages through the existing customer-facing filter
- [ ] T052 [US2] Implement the list and detail views in `apps/portal/views.py`, refusing anything not the customer's as not-found
- [ ] T053 [P] [US2] Create `templates/portal/requests.html` and `request_detail.html`
- [ ] T054 [US2] Extract and translate this phase's strings, then check both domains
- [ ] T055 [US2] Demonstrate the boundary fails when broken: make the detail view read the staff message filter, confirm T047 and the internal-visibility sweep both fail; restore

**Checkpoint**: the portal is useful. This is the smallest version worth shipping.

---

## Phase 5: User Story 3 - Replying (Priority: P2)

**Goal**: A customer replies from the portal and the agent sees it like any other reply.

**Independent Test**: Reply, and confirm the agent's view and the ticket's state both respond as they do to email.

### Tests for User Story 3

- [ ] T056 [P] [US3] Write `apps/portal/tests/test_reply.py` asserting a reply joins the conversation, attributed to the customer and marked as coming from the portal (FR-020, FR-021)
- [ ] T057 [P] [US3] Extend `test_reply.py` asserting a reply to a request awaiting the customer stops it waiting, identically to an emailed reply (FR-022)
- [ ] T058 [P] [US3] Extend `test_reply.py` asserting a reply to a resolved request reopens it, identically to an emailed reply
- [ ] T059 [P] [US3] Extend `test_reply.py` asserting empty and over-long content are refused with a reason naming which, and that nothing is written (FR-024)
- [ ] T060 [P] [US3] Extend `test_reply.py` asserting a reply directed at another customer's request is refused as not-found and writes nothing
- [ ] T061 [P] [US3] Extend `apps/portal/tests/test_rate_limits.py` asserting replies beyond the configured limit are refused, the customer is told when to try again, and nothing they wrote is lost
- [ ] T062 [P] [US3] Write `apps/portal/tests/test_reply_parity.py` asserting a portal reply and an emailed reply produce the same ticket state from the same starting state — the property that stops the two paths diverging

### Implementation

- [ ] T063 [US3] Implement replying in `apps/portal/services/tickets.py`, calling the existing ticket services rather than reimplementing the transitions
- [ ] T064 [US3] Add the portal channel value in `apps/tickets/models.py` and its migration, confirming it alters no column
- [ ] T065 [US3] Implement the reply view in `apps/portal/views.py` with validation and rate limiting
- [ ] T066 [P] [US3] Add the reply composer to `templates/portal/request_detail.html`
- [ ] T067 [US3] Extract and translate this phase's strings, then check both domains

**Checkpoint**: the loop closes — a customer can answer without leaving the portal.

---

## Phase 6: User Story 4 - Raising a request (Priority: P2)

**Goal**: A signed-in customer opens a request without retyping who they are.

**Independent Test**: Raise one; confirm it appears in their list at once and in the agent queue like any other.

### Tests for User Story 4

- [ ] T068 [P] [US4] Write `apps/portal/tests/test_new_request.py` asserting a signed-in customer is not asked for their name or email (FR-023)
- [ ] T069 [P] [US4] Extend `test_new_request.py` asserting the request is attached to their contact, appears in their list immediately, and reaches the agent queue marked as coming from the portal
- [ ] T070 [P] [US4] Extend `test_new_request.py` asserting a customer with no contact record yet gets one created by raising their first request
- [ ] T071 [P] [US4] Write `apps/intake/tests/` coverage asserting the anonymous request form behaves exactly as before — the portal adds a second path and must not change the first (FR-025)
- [ ] T072 [P] [US4] Extend `apps/portal/tests/test_rate_limits.py` for new requests

### Implementation

- [ ] T073 [US4] Implement raising a request in `apps/portal/services/tickets.py`, reusing the intake service rather than duplicating it
- [ ] T074 [US4] Implement the view in `apps/portal/views.py` with validation and rate limiting
- [ ] T075 [P] [US4] Create `templates/portal/new_request.html`
- [ ] T076 [US4] Extract and translate this phase's strings, then check both domains

**Checkpoint**: full self-service. A customer never needs the anonymous form again.

---

## Phase 7: User Story 5 - Recovering a password (Priority: P2)

**Goal**: A customer who cannot sign in gets back in, without help.

**Independent Test**: Request a reset, follow it, sign in with the new password; confirm the old one and the used link both stop working.

### Tests for User Story 5

- [ ] T077 [P] [US5] Write `apps/portal/tests/test_password_reset.py` asserting a single-use message is sent, and that the response is identical for an address with no account (FR-007)
- [ ] T078 [P] [US5] Extend `test_password_reset.py` asserting a used link and an expired link both stop working, with a way to request another
- [ ] T079 [P] [US5] Extend `test_password_reset.py` asserting the previous password stops working and other sessions for that account end (FR-012)
- [ ] T080 [P] [US5] Extend `test_password_reset.py` asserting the new password is held to the same policy as registration
- [ ] T081 [P] [US5] Write `apps/portal/tests/test_lockout.py` asserting repeated failures lock the account for the configured period and the owner is told (FR-011)
- [ ] T082 [P] [US5] Extend `test_lockout.py` asserting a lockout does not reveal whether the address has an account

### Implementation

- [ ] T083 [US5] Implement reset in `apps/portal/services/passwords.py`, including the identical-response rule and ending other sessions
- [ ] T084 [US5] Implement lockout in `apps/portal/services/passwords.py`
- [ ] T085 [US5] Implement the reset views in `apps/portal/views.py` and route them
- [ ] T086 [P] [US5] Create `templates/portal/reset.html` and `reset_confirm.html`, and the reset and lockout emails in both languages
- [ ] T087 [US5] Extract and translate this phase's strings, then check both domains

**Checkpoint**: a forgotten password is no longer a support request.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T088 Demonstrate every check this feature added fails when its defect is reintroduced (FR-038): the staff refusal, the scope-independence of that refusal, the confirmation gate, the identical-response rule, the internal-message boundary, the reply parity. Record what was broken and what failed in [quickstart.md](quickstart.md)
- [ ] T089 [P] Extend `tests/e2e/test_rtl_layout.py` and `tests/e2e/test_accessibility.py` with the portal screens
- [ ] T090 [P] Extend `tests/e2e/test_mobile_layout.py` with the portal screens — a customer checking a request is the likeliest reader in this product to be on a phone
- [ ] T091 [P] Extend `tests/e2e/test_arabic_sweep.py` with the portal screens, signed out and signed in, since signed-out screens were missed once already
- [ ] T092 [P] Review `apps/portal/` for business logic in views rather than services, and for any read that bypasses the customer-facing filter
- [ ] T093 [P] Document the portal in `docs/agent-guide.md` in both languages: what a customer can see and do, so an agent knows what the person on the other end is looking at
- [ ] T094 [P] Update `docs/production-readiness.md`: the portal makes email delivery customer-facing, and adds a public sign-in to a product that had none
- [ ] T095 Run all twelve scenarios in [quickstart.md](quickstart.md) in both languages
- [ ] T096 Confirm `tools/catalog.py status` and `tools/catalog.py placeholders` report both domains clean

---

## Dependencies & Execution Order

### Phase order

```text
Phase 1 Setup — the sweep, before the templates it sweeps
   └─▶ Phase 2 Foundational + US6 (P1) ⚠️ blocks everything
          │      the account, the session, and the refusal built together
          ├─▶ Phase 3 US1 (P1) 🎯 identity
          │      └─▶ Phase 4 US2 (P1)   the smallest portal worth shipping
          │             ├─▶ Phase 5 US3 (P2)   replying
          │             └─▶ Phase 6 US4 (P2)   raising
          └─▶ Phase 7 US5 (P2)   reset needs the link machinery from US1
                 └─▶ Phase 8 Polish
```

### Hard ordering constraints

1. **Phase 1 before any portal template.** Adding customer-facing templates under a sweep that
   does not cover them is how one ships unswept.
2. **Phase 2 before everything.** There is no "their own" before there is a customer, and the
   staff refusal is a property of the session rather than a check added afterwards.
3. **T008 is the test this architecture exists for.** Forcing a department onto a customer
   account and confirming the refusals hold is what distinguishes "a customer is refused" from
   "a customer happens to have no scope". It is not optional and it is not deferrable.
4. **US1 before US2.** A list of "their own" requests needs a confirmed address to be *whose*.
5. **US1 before US5.** Reset reuses the single-use expiring link built for confirmation.

### What is NOT ordered

US3 and US4 are independent of each other once US2 exists. US5 needs only US1.

### Parallel opportunities

- Every task marked [P] within a phase touches a different file.
- US3 and US4 can proceed simultaneously after US2.
- US5 can proceed in parallel with US2 once US1 is done.

---

## Implementation Strategy

### The smallest portal worth shipping

1. Phase 1 — the sweep
2. Phase 2 — the account, the session, and the refusal
3. Phase 3 — registration and sign-in
4. Phase 4 — the list and the detail
5. **Stop and validate**: quickstart scenarios 1 to 7, including scenario 6 with a department forced onto the account
6. Ship. A customer can see what is happening with their requests, which is the thing they wanted.

### Then

7. Phase 5 (US3) — replying, which closes the loop
8. Phase 6 (US4) — raising, which retires the anonymous form for signed-in customers
9. Phase 7 (US5) — reset, so a forgotten password stops being a support request
10. Phase 8 — prove every check fails, and run the twelve scenarios in both languages

### Before any of it reaches customers

Email delivery must work. Eight of the twelve scenarios end in a message arriving, and
`docs/email-setup.md` has not been actioned. The portal can be **built** against a console
backend; it cannot be **released** against one, and discovering that late is the most likely
way this feature slips.

---

## Notes

- [P] = different files, no dependency.
- Every phase ends with translation extraction, in **both** domains. A phase that adds a string
  and defers its translation is a phase that shipped an English string into an Arabic screen —
  and this project has done that twice.
- Clear the rate limiter's cache between tests. It has leaked here before, and the symptom is a
  suite that passes and fails by ordering.
- Commit after each task or logical group. Stop at any checkpoint.
