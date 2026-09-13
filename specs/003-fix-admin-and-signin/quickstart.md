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

## Scenario run (T074), 2026-09-13

| # | Scenario | Automated | By hand, both languages |
|---|---|---|---|
| 1 | Scope default: the account is visible afterwards | 5 passed | ✔ browser |
| 2 | An out-of-scope account is refused | 10 passed | — |
| 3 | A scopeless administrator is told what is wrong | 18 passed | — |
| 4 | A new installation reaches a working administrator | 7 passed | — |
| 5 | Arabic everywhere, including after the page loads | 12 passed | ✔ browser |
| 6 | A wrong translation is caught | 19 passed | — |
| 7 | Language before signing in | 10 passed | ✔ browser, ar + en |
| 8 | Quick sign-in, and its absence | 16 passed | ✔ browser |
| 9 | The audit log is readable | 13 passed | ✔ browser, Arabic |

Every scenario has automated coverage that fails when its defect is reintroduced (see the
table below). Five were also opened in a browser during the work, and **four of the problems
fixed in this feature were found that way rather than by a failing test**: two English strings
on an otherwise Arabic sign-in screen, `last_login` rendering as an English identifier, the
audit log's action column, and every reference truncating from the wrong end. All four were
invisible to a green suite.

Scenarios 2, 3, 4 and 6 have not been walked through by a person in both languages. They are
the ones where the observable outcome is a refusal or a command's output rather than a screen
someone reads, so the automated coverage is closer to the whole story — but that is a reason
to rank them last, not a reason to call them done.

## What was demonstrated (T070)

FR-021 asks that every check this feature adds be seen to fail against the defect it guards.
Each row below was produced by breaking one thing, running the tests that should notice, and
restoring. Run again with `/tmp/claude-1000/mut/run.sh` or by hand.

| What was broken | What failed |
|---|---|
| The add-account scope default removed | 1 test |
| An out-of-scope account silently corrected instead of refused | 6 tests |
| The missing-scope explanation suppressed | 7 tests |
| A scopeless account treated as seeing everything (the escalation) | 2 tests |
| The placeholder rule neutered to find nothing | 2 tests |
| The client catalog loaded after the scripts that call it | 1 test |
| The production quick-sign-in gate reading the environment | 2 tests |
| Quick sign-in trusting the hidden button instead of the setting | 1 test |
| The audit log showing creations field by field | 2 tests |
| An audit field losing its label | 1 test |

**Two of these found nothing on the first attempt, and both were real gaps rather than
noise.**

*The scope default* could be removed with every test still passing. The assertion searched
the whole page for `value="1" selected`, and the department and branch happen to share a
primary key in these fixtures — so the branch field was satisfying the department's
assertion. The assertion now reads the `<select>` it is about.

*The placeholder rule* could be neutered to find nothing with every test still passing. Every
test of it asked whether the catalogs were clean, and with the catalogs clean "found nothing"
and "cannot find anything" are indistinguishable. There are now tests that hand the rule a
synthetic catalog it must find a fault in — the rule is checked, not only its subject.

That is this feature's own theme arriving from the other direction: a check that can only
detect absence will report correctness. It was worth running the sweep for those two alone.

**A third attempt reported no failures for a different reason**, worth recording because it
is the trap in this technique: two mutations silently never applied — one lost its escaping
in a shell heredoc, the other had the wrong indentation. A mutation that does not apply looks
exactly like a mutation the tests survived. Every patch now asserts it matched before the
tests run.

## Definition of done for any task in this feature

- A test written first, seen to fail for the right reason, then passing.
- Every check this feature adds demonstrated to fail when its defect is reintroduced (FR-021).
- Both catalogs complete, with no entry introducing a placeholder its source lacks.
- Nothing about a stored audit entry altered.
