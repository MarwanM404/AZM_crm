# Feature Specification: Administration visibility, bilingual correctness, and the sign-in screen

**Feature Branch**: `003-fix-admin-and-signin`

**Created**: 2026-09-13

**Status**: Draft

**Input**: Five defects reproduced against a seeded database on 2026-09-13, plus a request to make the sign-in screen match the product and support role testing.

## Context

Every defect here was reproduced, not inferred. Two of them share a shape worth naming before
the stories, because it explains why a suite of 719 passing tests did not catch either.

**The system succeeded unhelpfully.** An administrator created an account in a department they
cannot see. Nothing failed: scoping worked exactly as designed, the account was written, the
redirect happened. The administrator was told the work succeeded, and the result was invisible
to them. No error existed to report.

**A check that detects absence will not detect wrongness.** The Arabic catalog contains a
translation for `Reference` that is actually the email reply subject, so a table header renders
the literal text `رد: %(REFERENCE)S`. Nothing flags the entry as uncertain, so the automated
checks report both catalogs complete and correct. Everything built so far asks
"is a translation present?" and nothing asks "is it the right one?".

Both themes become requirements in their own right (FR-020, FR-021), because fixing the two
instances without fixing the class leaves the next one to be found by a customer.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An administrator creates an account and can find it (Priority: P1)

An administrator adds a colleague's account. Either the account appears in the list afterwards,
or the administrator is told plainly why it will not — before it is created, not after.

**Why this priority**: This is the reported defect, and it is the worst kind. The administrator
believes the account exists and works; the colleague cannot sign in to a scope nobody
administers; and there is nothing on any screen to suggest anything went wrong. Every other
story here is cosmetic by comparison.

**Independent Test**: Create an account through the form without changing the department, and
confirm it is either visible in the list afterwards or refused with a reason at the point of
creating it.

**Acceptance Scenarios**:

1. **Given** an administrator on the add-account screen, **When** the form loads, **Then** the
   department and branch default to the administrator's own, not to whichever sorts first.
2. **Given** an administrator creating an account, **When** they submit it without changing the
   scope, **Then** the account is created in their own department and appears in the list.
3. **Given** an administrator who deliberately chooses a scope they do not administer, **When**
   they submit, **Then** the system refuses and says the account would not be visible to them,
   rather than creating something they cannot see.
4. **Given** an account has just been created, **When** the administrator returns to the list,
   **Then** the newly created account is identifiable — they can confirm the work landed
   without reading every row.
5. **Given** an administrator with no department or branch of their own, **When** they open the
   add-account screen, **Then** they are told their own account has no scope and what to do
   about it, rather than being shown a form whose result they cannot see.

---

### User Story 2 - An administrator without a scope is not silently blinded (Priority: P1)

An administrator whose own account has no department or branch — the state the very first
account on a new installation is left in, because nothing asks — sees every scoped screen
empty, including the list of staff accounts, which shows only themselves.

**Why this priority**: Equal to Story 1 and for the same reason: nothing reports it. The
product looks empty and broken to the one person who can fix it, and the first account created
on a new installation is exactly this account. It is the first experience anyone has of the
system.

**Independent Test**: Sign in as an account with no department or branch, open the staff
accounts list and the ticket queue, and confirm the state is explained rather than presented as
an empty product.

**Acceptance Scenarios**:

1. **Given** an administrator with no department or branch, **When** they open any scoped
   screen, **Then** the emptiness is explained as a missing scope on their own account, not
   presented as "there is nothing here".
2. **Given** such an administrator, **When** they read the explanation, **Then** it tells them
   how to give their account a scope.
3. **Given** an administrator with a department and branch, **When** they open the same
   screens, **Then** nothing about this explanation appears.
4. **Given** a new installation, **When** the first administrator account is created by
   whatever means, **Then** either it is given a department and branch, or the gap is reported
   at the moment it is created rather than discovered later.

---

### User Story 3 - The interface is genuinely Arabic (Priority: P2)

An Arabic-speaking member of staff uses the product and finds no English text, no raw
placeholder codes, and no untranslated strings arriving from the browser.

**Why this priority**: FR-031 of the MVP promised a bilingual product at launch, and today it
is bilingual only where the server renders. Below that promise sits a header displaying
`رد: %(REFERENCE)S`, which does not read as a missing translation — it reads as a broken
product.

**Independent Test**: Open every screen in Arabic and confirm no Latin text and no format
placeholder appears in any label, heading, control or status message, including ones that
change after the page has loaded.

**Acceptance Scenarios**:

1. **Given** a member of staff reading Arabic, **When** they open the live chat console,
   **Then** every column heading is Arabic and none contains a placeholder code.
2. **Given** the same person, **When** a status changes in front of them — going online,
   being refused, a queue position moving — **Then** the new text is Arabic too.
3. **Given** the same person on the administration screens, **When** they choose a department
   or branch, **Then** the names are shown in Arabic.
4. **Given** a translation exists for every string, **When** the catalogs are checked, **Then**
   a translation that introduces a placeholder its source does not have is reported as an
   error, not counted as complete.
5. **Given** a translated string is wrong in a way no automated check can see, **When** the
   catalogs are reviewed, **Then** the review is a recorded step rather than an assumption.

---

### User Story 4 - The sign-in screen looks like the product (Priority: P2)

Someone arriving at the sign-in screen sees the same product they will see after signing in —
branded, laid out, and readable in their own language before they have an account to read a
preference from.

**Why this priority**: It is the first screen anyone sees, including every customer's IT
department during evaluation. It is also the only screen where language cannot come from a
stored preference, so it is the one place a switcher is not optional.

**Independent Test**: Open the sign-in screen signed out, in both languages, and confirm it
carries the product's identity and can be switched between Arabic and English before signing in.

**Acceptance Scenarios**:

1. **Given** a signed-out visitor, **When** they open the sign-in screen, **Then** it carries
   the same branding and visual treatment as the screens behind it.
2. **Given** an Arabic speaker arriving at the sign-in screen, **When** the page loads, **Then**
   they can switch to Arabic without signing in first.
3. **Given** they switch language, **When** the page reloads, **Then** the choice survives
   into the session they are about to start.
4. **Given** a failed sign-in, **When** the error appears, **Then** it is presented in the same
   style as every other error in the product.

---

### User Story 5 - Signing in as each role for testing (Priority: P3)

Someone testing the product signs in as an agent, a supervisor or an administrator with one
click, and reaches the customer-facing screens without an account at all — and none of this
exists in a real deployment.

**Why this priority**: It saves time on every test run, which is worth real money over a
project, but it is a convenience. It is last because it is the only story here that adds
something rather than fixing something — and the only one that can do harm if it is wrong.

**Independent Test**: With the feature enabled, sign in as each role from the sign-in screen
without typing a password. With production settings, confirm there is nothing to click and no
route to sign in that way.

**Acceptance Scenarios**:

1. **Given** the quick sign-in is enabled, **When** someone opens the sign-in screen, **Then**
   they can sign in as an agent, a supervisor or an administrator in one action each.
2. **Given** the same screen, **When** they want to see what a customer sees, **Then** they are
   offered the customer-facing screens directly, because a customer has no account to sign into.
3. **Given** production settings, **When** the sign-in screen is rendered, **Then** no quick
   sign-in appears.
4. **Given** production settings, **When** a quick sign-in is requested directly rather than by
   clicking, **Then** it is refused — the absence of a button is not the protection.
5. **Given** production settings, **When** someone attempts to enable the feature by
   configuration, **Then** it stays disabled.
6. **Given** the feature is enabled, **When** it offers accounts, **Then** it offers only the
   demonstration accounts whose passwords are already public in this repository, and never an
   account belonging to a real person.

---

### User Story 6 - The audit log can be read (Priority: P3)

Someone reviewing the audit log can see who changed what, without wading through every field of
every record and internal names that mean nothing to them.

**Why this priority**: The audit log is a compliance obligation (MVP FR-027) that currently
fails at being useful rather than at being complete — the data is all there and unreadable.
Below the other stories because nothing is lost or wrong, only unusable.

**Independent Test**: Create a record, open the audit log, and find what changed in it without
horizontal scrolling or reading internal field names.

**Acceptance Scenarios**:

1. **Given** a record was created, **When** its audit entry is shown, **Then** it says the
   record was created rather than listing every field as having changed from nothing.
2. **Given** a record was changed, **When** its entry is shown, **Then** only the fields that
   actually changed are listed.
3. **Given** an entry is displayed, **When** field names are shown, **Then** they are the names
   a person would recognise, in their own language, not internal identifiers.
4. **Given** an entry with many changes, **When** it is displayed, **Then** the table stays
   readable and the row does not grow without limit.

---

### Edge Cases

- What happens when the only administrator has no scope and no other administrator exists to
  give them one? The system must not require an already-scoped administrator to fix a missing
  scope, or a new installation cannot be recovered from its own first screen.
- What happens when every department is one the administrator does not administer — can they
  create any account at all? They must be able to create accounts in their own scope; that is
  the whole of what they administer.
- What happens when an account already exists outside the administrator's scope, created before
  this change? It must remain reachable by someone, and the fix must not orphan it further.
- What happens when a quick sign-in account has been deleted or renamed since the demonstration
  data was seeded? The offer must fail visibly rather than signing someone in as the wrong
  person.
- What happens when a translation is wrong but introduces no placeholder — a plausible Arabic
  sentence with the wrong meaning? No automated check can catch this; the requirement is that
  the limit is stated rather than assumed away.
- What happens to client-side text when the translation catalog cannot be loaded? It must fall
  back to the source language rather than showing nothing.

## Requirements *(mandatory)*

### Administration visibility

- **FR-001**: System MUST default the department and branch on the add-account screen to the
  acting administrator's own.
- **FR-002**: System MUST refuse to create an account in a scope the acting administrator does
  not administer, and MUST say why rather than failing silently.
- **FR-003**: System MUST confirm a created account to the administrator in a way that
  distinguishes it from the accounts that were already there.
- **FR-004**: System MUST explain an empty scoped screen when the emptiness is caused by the
  acting user having no department or branch, rather than presenting it as no data.
- **FR-005**: System MUST make an administrator with no scope able to reach a state where they
  have one, without requiring a second, already-scoped administrator.
- **FR-006**: System MUST NOT allow a staff account to be created without a department and a
  branch by any route, including routes that bypass the administration screens.

### Bilingual correctness

- **FR-007**: System MUST present every interface string in the reader's language, including
  strings produced after the page has loaded.
- **FR-008**: System MUST show department and branch names in the reader's language wherever
  they appear.
- **FR-009**: System MUST NOT display a format placeholder to a user under any circumstances.
- **FR-010**: System MUST reject a translation that introduces a format placeholder absent from
  its source string, as an automated check that fails, not as a review convention.
- **FR-011**: System MUST fall back to the source language when client-side translations are
  unavailable, rather than showing empty or missing text.
- **FR-012**: System MUST allow the interface language to be changed before signing in.

### The sign-in screen

- **FR-013**: System MUST present the sign-in screen with the same branding and visual
  treatment as the rest of the product.
- **FR-014**: System MUST carry a language chosen before signing in into the session that
  follows.

### Quick sign-in for testing

- **FR-015**: System MUST be able to offer one-action sign-in as each staff role, and a direct
  route to the customer-facing screens, which have no account.
- **FR-016**: System MUST disable quick sign-in by default.
- **FR-017**: System MUST make quick sign-in unavailable in production regardless of
  configuration — no deployment setting, override or mistake may switch it on there.
- **FR-018**: System MUST refuse a quick sign-in request that is made directly rather than
  through the interface, when the feature is disabled. Hiding the control is not the control.
- **FR-019**: System MUST offer only accounts created as demonstration data, never an account
  belonging to a real person.

### The two themes

- **FR-020**: System MUST NOT complete an action whose result the acting user cannot then see,
  without telling them so at the time.
- **FR-021**: Every check introduced by this feature MUST be demonstrated to fail when the
  defect it guards against is reintroduced deliberately. A check nobody has seen fail is a
  claim, not a guarantee — the catalog checks reported both languages correct while a heading
  displayed a raw placeholder.

### The audit log

- **FR-022**: System MUST present a record's creation as a creation, not as every field
  changing from nothing.
- **FR-023**: System MUST list only the fields that changed.
- **FR-024**: System MUST show field names in language a reader recognises, translated, and
  MUST NOT show internal identifiers.
- **FR-025**: System MUST keep an audit entry readable regardless of how many fields it
  touches.

## Key Entities

- **Staff account**: a person who signs in. Carries a role, a department and a branch. The
  department and branch decide what they can see; an account without them can see nothing,
  which is the subject of User Story 2.
- **Department, Branch**: the two dimensions of scope. Both already carry a name in each
  language; only one of those names is currently used.
- **Translation catalog**: the set of translated strings for a language. Currently checked for
  completeness and for uncertainty, and not for correctness.
- **Audit entry**: a record that something changed — who, when, and which fields moved from
  what to what. Complete today, unreadable today.
- **Demonstration account**: a staff account created as sample data, whose password is public
  in this repository. The only account quick sign-in may ever offer.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An administrator creating an account finds it in the list 100% of the time, or is
  told at the point of creating it why they will not.
- **SC-002**: A new installation reaches a working, scoped administrator without anyone
  manipulating stored data by hand.
- **SC-003**: No screen, in either language, displays text in the other language or a format
  placeholder — verified across every screen, including text that appears after the page loads.
- **SC-004**: A translation carrying a placeholder its source lacks is rejected automatically,
  before anyone sees it.
- **SC-005**: Someone testing signs in as any of the three roles in one action, and reaches the
  customer-facing screens without an account.
- **SC-006**: Quick sign-in is unreachable under production settings by every route, including
  a direct request and a configuration file attempting to enable it.
- **SC-007**: A reviewer finds what changed in an audit entry without horizontal scrolling.
- **SC-008**: An Arabic speaker can switch the sign-in screen to Arabic before signing in, and
  the choice survives into their session.

## Assumptions

- The role set stays Agent, Supervisor and Administrator. There is no customer account: visitors
  are anonymous until the portal phase, so "testing as a customer" means reaching the public
  screens, not signing in.
- Quick sign-in is for development and for a reviewer's own machine. If it is ever wanted on a
  shared staging deployment, that is a separate decision requiring its own gate; this spec
  assumes it is not, and that production is the only environment that must be proven safe.
- The demonstration accounts' passwords are already public in this repository, so quick sign-in
  discloses nothing that is not already disclosed. This stops being true the moment anyone
  points it at a real account, which FR-019 forbids.
- Refusing to create an out-of-scope account (FR-002) is preferred over silently redirecting it
  into the administrator's own scope, because an administrator who deliberately chose a
  department meant something by it.
- An administrator administers their own department and branch only. FR-023 of the MVP makes no
  exception for role, and this spec does not create one — an administrator who needs to manage
  another department is given an account there.
- Existing accounts already created out of scope are rare (this defect is new) and are handled
  as data, not by a migration path in code.
- The audit log's underlying data is correct and complete. This spec changes only how it is
  read; no audit entry is altered, and none can be (MVP FR-028).
