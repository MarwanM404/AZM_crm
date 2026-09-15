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

---

## The mutation record (T088, FR-038)

FR-038 asks that every check this feature adds be **demonstrated** to fail against the defect
it guards, not asserted to. The record below is an observation, produced by `tools/mutate.py`,
which breaks each guarantee in turn, runs the tests, restores the file, and refuses to report
anything if a patch did not match — a mutation that fails to apply reports the codebase as
perfectly defended, and spec 003 shipped two of those.

Reproduce it with:

```bash
.venv/bin/python tools/mutate.py
```

Run on 2026-09-15. Every mutation was detected, and the suite was confirmed green afterwards.

| Defect reintroduced | Checks that noticed |
|---|---|
| A customer session satisfies the deny-by-default wall anywhere, not only on portal paths | 4 |
| The portal signs a staff member out instead of refusing them | 3 |
| An account that has not proved its address may use the portal | 6 |
| Registration answers differently for an address that already has an account | 2 |
| The request detail reads the staff message filter instead of the customer one | 2 |
| The detail template is handed the ticket, so it can walk to an internal note | 7 |
| The request list filters by organization, so colleagues' requests appear | 6 |
| The portal decides the reply's effect on the ticket rather than sharing the rule | 2 |
| Somebody else's request is refused as forbidden rather than as not found | 2 |
| The strength check is given no account, so the similarity validator approves everything | 1 |
| A password change leaves every other session alive | 1 |
| The lock opens for the correct password | 3 |
| The portal ignores the language the customer chose | 1 |
| Customer-authored content is accepted at any length | 5 |
| A new contact's language preference is dropped | 2 |

### What the counts mean, and do not mean

A high count is not reassurance. "The detail template is handed the ticket" breaks seven checks
because the change also breaks unrelated rendering; the check that matters is the single one
asserting the context contains no ticket at all.

The rows worth watching are the ones reading **1**. Each of those guarantees rests on exactly
one test, and deleting that test would leave the defect undetectable:

- **The password policy** — `test_a_password_like_the_address_is_refused`. With `user=None`
  the similarity validator finds nothing to compare and approves everything, silently. This is
  the most dangerous row in the table: the mutation is a plausible simplification, the failure
  is invisible, and one test stands between them.
- **Other sessions surviving a reset** — `test_other_sessions_end`. The reset appears to work
  perfectly; only somebody else's already-open session tells you it did not.
- **The customer's language** — `test_an_arabic_customer_gets_an_arabic_page`. Found originally
  by taking a screenshot, after thirty-nine tests passed over it.

### Mutations that were NOT detected when first tried

Recorded because the table above only shows the end state.

- **A new contact's language preference dropped** passed all 190 tests when first mutated
  during User Story 4. Nothing fails when it is missing: the contact is created, the ticket is
  created, and the confirmation goes out in the right language. Only the desk's replies weeks
  later arrive in the wrong one. The test written to cover it then passed *while the
  assignment was still deleted*, because it used Arabic — the model default. Only the English
  case discriminates.

---

## What automation covers, and what still needs a person (T095)

T095 asks for the twelve scenarios to be walked in both languages. Most of the mechanics are
now covered by `tests/e2e/test_portal_journey.py`, which walks register → confirm from the
message → sign in → raise → reply → sign out → reset → sign in again, in Arabic and in English,
in a real browser.

That is not the same as somebody having used it. The table separates the two honestly, because
"the scenarios were run" meaning "a test passed" is the kind of claim that makes a release
sound safer than it is.

| # | Scenario | Covered by | Still needs a person |
|---|---|---|---|
| 1 | Register and confirm | `test_portal_journey`, `test_registration`, `test_confirmation` | Does the message read like it came from a company you trust? |
| 2 | An address that already has an account | `test_registration` (responses compared as text) | — |
| 3 | Sign in, unconfirmed and confirmed | `test_sign_in` | — |
| 4 | See your own requests | `test_request_list`, `test_portal_journey` | Is the status wording meaningful to somebody outside the desk? |
| 5 | Somebody else's request | `test_request_detail` | — |
| 6 | A customer is not staff | `test_staff_routes_refuse_customers` (including with a department forced onto the account) | — |
| 7 | Internal notes never appear | `test_request_detail`, `test_internal_visibility`, `test_arabic_sweep` | — |
| 8 | Reply, and the agent sees it | `test_reply`, `test_reply_parity`, `test_portal_journey` | Does the agent notice the portal channel mark, and does it change what they do? |
| 9 | Raise a request | `test_new_request`, `test_portal_journey` | Are the category names the ones a customer would pick? |
| 10 | Limits hold | `test_rate_limits`, `test_lockout` | Does a rate-limit refusal read as "wait a moment" rather than "you are blocked"? |
| 11 | Arabic, end to end | `test_arabic_sweep`, `test_rtl_layout`, `test_portal_journey` | **Does the Arabic read naturally?** See below. |
| 12 | Deactivation ends it | `test_account_deactivation` | — |

### Scenario 11 is the one that is NOT done

Automation can say there is no Latin text on an Arabic screen, no placeholder code, and that
the layout has mirrored. It cannot say whether the Arabic is any good.

Every Arabic string in this feature was written during implementation and reviewed by nobody
who speaks Arabic as a first language. The catalog reports complete; that means present, not
correct. Five of six fuzzy guesses were wrong in one story alone, including "I already have an
account" merged to "إنشاء الحساب" — *create the account*, the opposite instruction, on a
sign-in page. Those were caught by reading them. Nothing catches the ones that are merely
stilted.

**Before release, an Arabic speaker should read every portal screen and every portal email.**
That is a smaller task than it sounds — six screens and four messages — and it is the only part
of scenario 11 that matters.

### The email scenarios cannot be run at all yet

Eight of the twelve end in a message arriving, and `docs/email-setup.md` has not been actioned.
They pass here against a console backend, which proves the message was composed and addressed
correctly and proves nothing about delivery. See
[production-readiness.md](../../docs/production-readiness.md) §3.
