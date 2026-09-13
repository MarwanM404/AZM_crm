# Quickstart — validating this feature

Nine scenarios. Each one begins by reproducing the defect, because a fix that was never seen to
fix anything is a claim (FR-021).

## Prerequisites

The application running locally with demonstration data seeded, and both interface languages
compiled.

## Validation scenarios

### 1. An account created without touching the scope is visible afterwards (FR-001, US1)

Sign in as an administrator. Add an account, filling in only a name and an email. Confirm the
department and branch already show the administrator's own, and that the account appears in the
list immediately afterwards.

*Before the fix*: the scope defaults to whichever department sorts first, and the account is
created somewhere the administrator cannot see.

### 2. An account that would be invisible is refused (FR-002, US1)

Add an account and deliberately choose a different department. Confirm it is refused, that the
message says the account would not be visible, and that no account was created.

### 3. A scopeless administrator is told what is wrong (FR-004, FR-005, US2)

Sign in as an administrator with no department or branch. Confirm the ticket queue, the customer
list and the staff accounts list each explain that the account has no scope rather than
appearing empty, and that the explanation leads somewhere that fixes it.

### 4. A new installation reaches a working administrator (FR-006, US2)

From an empty database, create the first administrator by the documented route. Confirm it has
a department and a branch without anyone editing stored data by hand.

### 5. The interface is Arabic everywhere, including after the page loads (FR-007, FR-009, US3)

In Arabic, open the live chat console. Confirm every column heading is Arabic and none shows a
placeholder code. Go online, then attempt to go offline while holding a conversation, and
confirm both the status and the refusal are Arabic.

*Before the fix*: the reference column reads `رد: %(REFERENCE)S` and the status reads `Offline`.

### 6. A wrong translation is caught (FR-010, US3)

Edit an Arabic translation so it contains a placeholder its source does not have. Confirm the
check fails and names the entry. Restore it and confirm the check passes.

This is the scenario that proves the class is closed rather than the instance.

### 7. Language before signing in (FR-012, FR-014, US4)

Signed out, open the sign-in screen. Switch to Arabic, confirm it takes effect immediately, then
sign in and confirm the session is still Arabic.

### 8. Quick sign-in, and its absence (FR-015 – FR-019, US5)

With the feature enabled, sign in as each of the three roles in one action, and reach the
customer-facing screens without an account.

Then, with production configuration: confirm no control appears, **and** that requesting the
route directly is refused. Do both — the second is the one that matters, and the one that looks
unnecessary once the first passes.

### 9. The audit log is readable (FR-022 – FR-025, US6)

Create a ticket and change its status. In the audit log, confirm the creation says it was
created rather than listing every field, the change lists only the status, field names are in
the reader's language, and no row requires horizontal scrolling.

## Definition of done for any task in this feature

- A test written first, seen to fail for the right reason, then passing.
- Every check this feature adds demonstrated to fail when its defect is reintroduced (FR-021).
- Both catalogs complete, with no entry introducing a placeholder its source lacks.
- Nothing about a stored audit entry altered.
