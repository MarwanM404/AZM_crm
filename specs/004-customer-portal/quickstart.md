# Quickstart — validating the customer portal

Twelve scenarios. Several begin by trying to do something that should not work, because most of
this feature's risk is in what it refuses rather than what it does.

## Prerequisites

The application running locally with demonstration data seeded, both catalogs compiled, and
**email delivery working**. That last one is not a formality: eight of the twelve scenarios end
in a message arriving. Until `docs/email-setup.md` has been actioned, run them against the
console email backend and understand that you have tested the composing and not the delivery.

## Validation scenarios

### 1. Register, confirm, sign in (US1)

Register with an address that has never written in. Confirm you cannot sign in yet. Follow the
message, then sign in. The whole path should take under three minutes.

### 2. The registration screen does not answer questions (US1, FR-007)

Register an address that already has an account. Confirm the response is indistinguishable from
the first registration, that no account is created, and that a message reaches the address
telling its owner what happened.

Then do the same with an address that has open tickets, and confirm nothing about them is
disclosed on screen.

### 3. A link works once (US1, US5)

Follow a confirmation link twice. Follow a reset link twice. Let one expire and follow it.
Each refusal should offer a way to get a new one.

### 4. The list shows their requests and only theirs (US2)

Sign in as a customer with tickets. Confirm reference, subject, status and dates are all
present. Then take a reference belonging to somebody else and request it directly: it must be
**not found**, and indistinguishable from a reference that does not exist.

### 5. Internal notes are not there (US2, FR-016)

Put an internal note on a customer's ticket. Open that ticket in the portal, in both languages,
and read the page — and the page source. The note must not appear in either.

### 6. A customer is not staff (US6) — the one that matters

Signed in as a customer, request the ticket queue, the customer list, the chat console, the
audit log and the staff sign-in. Each must refuse.

Then force a department onto the customer account by whatever means the implementation allows,
and repeat. If anything now succeeds, the refusal was resting on the missing scope rather than
on the account being a customer, and FR-028 is not met.

### 7. Staff are not customers (US6, FR-030)

Signed in as an agent, open the portal. It must refuse: a member of staff is not a customer of
the desk they work at.

### 8. A reply behaves like an emailed reply (US3)

Reply from the portal to a ticket that is awaiting the customer. Confirm the agent sees it
attributed to the customer and marked as coming from the portal, and that the ticket stops
waiting. Then reply to a resolved ticket and confirm it reopens.

### 9. A new request from the portal (US4)

Raise one while signed in. Confirm you were not asked for your name or email, that it appears
in your own list at once, and that it reaches the agent queue like any other.

Then open the public request form signed out and confirm it works exactly as before.

### 10. Limits hold (FR-010, FR-011)

Exceed the configured limit on registration, on sign-in, on reset and on replying. Each must
refuse and say when to try again. Confirm a locked account tells its owner, and that nothing a
customer had typed is lost.

### 11. Arabic, end to end (FR-033)

Do scenarios 1, 4 and 8 in Arabic. Every screen, and every message that arrives, must be
Arabic, right to left, with no Latin text and no placeholder codes.

### 12. Deactivation ends it (FR-031)

Deactivate a customer account while they are signed in. Their next request must be refused.

## Definition of done for any task in this feature

- A test written first, seen to fail for the right reason, then passing.
- Every check this feature adds demonstrated to fail when its defect is reintroduced (FR-038).
- Both catalogs complete in both domains, with no placeholder mismatch.
- No migration that alters a column on `Ticket`, `Message`, `Contact` or `User`.
