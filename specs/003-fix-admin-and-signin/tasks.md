---

description: "Task list for administration visibility, bilingual correctness, and the sign-in screen"
---

# Tasks: Administration visibility, bilingual correctness, and the sign-in screen

**Input**: Design documents from `/specs/003-fix-admin-and-signin/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Mandatory, not optional. Constitution I makes test-first non-negotiable and requires
every bug fix to begin with a regression test reproducing the defect. FR-021 goes one step
further: every *check* this feature adds must be demonstrated to fail when its defect is
reintroduced deliberately. That second requirement is why several phases below end with a task
that breaks the thing on purpose.

**Organization**: Grouped by user story. Each story is independently implementable and testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: The user story this serves (US1–US6)

---

## Phase 1: Setup

**Purpose**: Nothing to scaffold. This is a defect feature in an existing application; every
file it touches already exists except one command. These two tasks exist so the defects are
reproducible on demand rather than from memory.

- [X] T001 Write `tests/test_reported_defects.py` reproducing all five findings as failing tests: an account created out of scope is absent from its creator's list, a scopeless administrator sees only itself, the Arabic catalog contains a translation carrying a placeholder its source lacks, the chat console renders an untranslated client string, and an audit entry for a creation lists every field
- [X] T002 Confirm every test in `tests/test_reported_defects.py` fails for the reason stated, and record each failure message as a docstring in that file, so a later passing run cannot be mistaken for coverage that was always green

**Checkpoint**: five failing tests, each naming a defect a user reported.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: One thing, and it blocks the phases that add new strings.

**⚠️ Ordering constraint from [plan.md](plan.md)**: User Stories 4 and 6 both add translatable
strings. Adding strings under a check that cannot see a wrong translation is exactly how the
`Reference` entry arrived. The rule lands first.

- [X] T003 Implement the placeholder-mismatch rule in `tools/catalog.py`: a translation MUST NOT contain a format placeholder absent from its source string, reported per entry with the offending placeholder named
- [X] T004 Add the rule to `tests/test_translation_catalog.py` so it runs on every commit, not only when someone invokes the tool
- [X] T005 [P] Assert in `tests/test_translation_catalog.py` that a translation *omitting* a placeholder its source has is NOT reported — Arabic's zero, one and two plural forms legitimately drop the numeral, and five correct entries would fail a symmetric rule (see [research.md](research.md) §4)
- [X] T006 Demonstrate the rule fails: temporarily reintroduce the `Reference` mistranslation in `locale/ar/LC_MESSAGES/django.po`, confirm T004 fails and names it, restore

**Checkpoint**: a wrong translation can no longer be added silently. Stories may now add strings.

---

## Phase 3: User Story 1 - An administrator creates an account and can find it (Priority: P1) 🎯 MVP

**Goal**: An account an administrator creates is visible to them afterwards, or they are told at
the time why it will not be.

**Independent Test**: Create an account through the form without changing the department, and
confirm it appears in the list; then deliberately choose another department and confirm refusal.

### Tests for User Story 1

- [X] T007 [P] [US1] Write `apps/accounts/tests/test_account_scope_default.py` asserting the add-account form pre-selects the acting administrator's own department and branch, not whichever sorts first
- [X] T008 [P] [US1] Write `apps/accounts/tests/test_account_scope_refusal.py` asserting a submission naming another department is refused, explains that the account would not be visible, and creates nothing
- [X] T009 [P] [US1] Extend `apps/accounts/tests/test_account_scope_refusal.py` asserting the refusal is not a silent correction — the account is NOT created in the administrator's own scope instead (FR-020; see [research.md](research.md) §1)
- [X] T010 [P] [US1] Write `apps/accounts/tests/test_account_creation_confirmed.py` asserting a newly created account is identifiable in the list afterwards, distinguishable from accounts already there
- [X] T011 [P] [US1] Extend `apps/accounts/tests/test_account_scope_refusal.py` asserting an account cannot be created with no department or branch at all (FR-006)

### Implementation for User Story 1

- [X] T012 [US1] Default the department and branch to the acting administrator's own in `apps/accounts/views_admin.py` `user_new`
- [X] T013 [US1] Refuse an out-of-scope submission in `apps/accounts/views_admin.py`, with a message naming what would have happened, keeping the field visible and selectable rather than reducing it to one option
- [X] T014 [US1] Confirm a created account in `templates/accounts/users.html`, so the administrator can see the work landed without reading every row
- [X] T015 [US1] Extract and translate the new strings into `locale/ar/LC_MESSAGES/django.po` and `locale/en/LC_MESSAGES/django.po`, then check with `tools/catalog.py status`

**Checkpoint**: the reported defect is closed. This is shippable on its own.

---

## Phase 4: User Story 2 - An administrator without a scope is not silently blinded (Priority: P1)

**Goal**: An administrator whose own account has no department or branch is told so, and can fix
it — and a new installation never produces that account in the first place.

**Independent Test**: Sign in as a scopeless administrator, confirm each scoped screen explains
the cause; then create a first administrator from an empty database and confirm it has a scope.

### Tests for User Story 2

- [ ] T016 [P] [US2] Write `apps/accounts/tests/test_scopeless_administrator.py` asserting the staff accounts list, the ticket queue and the customer list each explain a missing scope rather than appearing empty
- [ ] T017 [P] [US2] Extend `apps/accounts/tests/test_scopeless_administrator.py` asserting the explanation appears for a scopeless user and NOT for a scoped one — an explanation shown to everybody explains nothing
- [ ] T018 [P] [US2] Write `apps/accounts/tests/test_scope_self_service.py` asserting a scopeless administrator can set their own scope, and that an administrator who already has one cannot change it (FR-005; the narrowing recorded in [plan.md](plan.md) Complexity Tracking)
- [ ] T019 [P] [US2] Extend `apps/accounts/tests/test_scope_self_service.py` asserting a scopeless account is NOT treated as seeing everything — the escalation this defect could have produced (Constitution III, [research.md](research.md) §2)
- [ ] T020 [P] [US2] Write `apps/accounts/tests/test_bootstrap_command.py` asserting the first-administrator command creates a department, a branch and an administrator together, and refuses to leave any of them missing

### Implementation for User Story 2

- [ ] T021 [US2] Implement the first-administrator command in `apps/accounts/management/commands/`, creating the scope and the account in one step because on an empty database there is no department to point at
- [ ] T022 [US2] Explain a scope-caused empty result in `templates/accounts/users.html` and the shared empty-state used by the ticket queue and customer list
- [ ] T023 [US2] Implement the one-time self-service scope change in `apps/accounts/views_admin.py`, permitted only from no scope and never between scopes
- [ ] T024 [US2] Document the first-run route in `README.md`, replacing any instruction that produces a scopeless account
- [ ] T025 [US2] Extract and translate this phase's strings, then check with `tools/catalog.py status`

**Checkpoint**: a new installation reaches a working administrator, and an existing broken one can recover.

---

## Phase 5: User Story 3 - The interface is genuinely Arabic (Priority: P2)

**Goal**: No English text, no placeholder codes, and no untranslated strings arriving from the
browser.

**Independent Test**: Open every screen in Arabic, including text that changes after load, and
find no Latin text and no placeholder.

### Tests for User Story 3

- [ ] T026 [P] [US3] Write `apps/accounts/tests/test_bilingual_names.py` asserting department and branch names render in the reader's language wherever they appear, falling back to the other name when one is blank
- [ ] T027 [P] [US3] Write `tests/test_client_translations.py` asserting the client-side catalog is served, and that the Arabic and English catalogs differ — serving a catalog is not the same as serving the right one
- [ ] T028 [P] [US3] Extend `tests/test_client_translations.py` asserting client text falls back to the source language when the catalog is unavailable, rather than rendering empty (FR-011)
- [ ] T029 [P] [US3] Write `tests/e2e/test_arabic_sweep.py` asserting no rendered screen in Arabic contains a format placeholder, and that the chat console's status and refusal text are Arabic after they change
- [ ] T030 [P] [US3] Extend `tests/test_translation_catalog.py` with a task recording that human review of meaning is a step, not an assumption — the rule from Phase 2 cannot see a fluent sentence with the wrong meaning (US3 scenario 5)

### Implementation for User Story 3

- [X] T031 [US3] Correct the `Reference` entry in `locale/ar/LC_MESSAGES/django.po` — **done in Phase 2**: the placeholder rule is a blocking gate and could not be left failing — currently the email reply subject, rendering `رد: %(REFERENCE)S` in the chat console heading
- [ ] T032 [US3] Add a display-name property to `Department` and `Branch` in `apps/accounts/models.py`, so the language choice is made once rather than at every display site
- [ ] T033 [US3] Use the display name wherever a department or branch is shown, starting with the administration dropdowns in `templates/accounts/`
- [ ] T034 [US3] Route the client-side translation catalog in `config/urls.py`, per active language and not cached across languages
- [ ] T035 [US3] Load the catalog in `templates/base.html` before the page scripts, so `gettextOrFallback` in `static/js/chat-console.js` finds a real `gettext` rather than always taking the fallback
- [ ] T036 [US3] Extract and compile both catalogs, then check with `tools/catalog.py status`

**Checkpoint**: the product is bilingual where it claimed to be, including after the page loads.

---

## Phase 6: User Story 4 - The sign-in screen looks like the product (Priority: P2)

**Goal**: The first screen anyone sees carries the product's identity, and can be read in either
language before there is an account to read a preference from.

**Independent Test**: Open the sign-in screen signed out in both languages and confirm it is
branded and switchable.

### Tests for User Story 4

- [ ] T037 [P] [US4] Write `apps/accounts/tests/test_sign_in_language.py` asserting an anonymous visitor can choose a language, that an unsupported code is refused, and that the choice takes effect immediately
- [ ] T038 [P] [US4] Extend `apps/accounts/tests/test_sign_in_language.py` asserting a language chosen while signed out is adopted by the account on successful sign-in (FR-014), resolving the mismatch where an account defaults to Arabic and an anonymous visitor to English
- [ ] T039 [P] [US4] Write `tests/e2e/test_sign_in_visual.py` asserting the sign-in screen carries the product's branding and layout, and that it does not scroll sideways on a phone
- [ ] T040 [P] [US4] Extend `tests/e2e/test_sign_in_visual.py` asserting a failed sign-in presents its error in the same style as errors elsewhere

### Implementation for User Story 4

- [ ] T041 [US4] Implement anonymous language selection in `apps/accounts/views.py` and route it in `apps/accounts/urls.py`, separate from the signed-in switcher which writes to an account that does not yet exist
- [ ] T042 [US4] Adopt a pre-sign-in language choice onto the account in `apps/accounts/views.py` `sign_in`
- [ ] T043 [US4] Rebuild `templates/accounts/sign_in.html` with the product's chrome, a card, branding and the language switch
- [ ] T044 [P] [US4] Add the sign-in screen's styles to `static/css/base.css`, placed after the rules they override — a media query adds no specificity, and an override written above its target loses
- [ ] T045 [US4] Extract and translate this phase's strings, then check with `tools/catalog.py status`

**Checkpoint**: the first screen anyone sees looks like the product, in either language.

---

## Phase 7: User Story 5 - Signing in as each role for testing (Priority: P3)

**Goal**: One-click sign-in as each staff role and a direct route to the customer-facing screens
— and none of it reachable in production.

**Independent Test**: With the feature enabled, sign in as each role without typing a password.
With production configuration, confirm no control appears **and** that the route itself refuses.

**⚠️ This is the only story here that can do harm.** Its tests are written around the failure
rather than the feature, and T047 matters more than T046.

### Tests for User Story 5

- [ ] T046 [P] [US5] Write `apps/accounts/tests/test_quick_sign_in.py` asserting that, when enabled, each of the three roles can be signed in as in one action
- [ ] T047 [P] [US5] Extend `apps/accounts/tests/test_quick_sign_in.py` asserting the route refuses when the feature is disabled, **called directly with no control rendered** — hiding a button does not disable the route behind it (FR-018)
- [ ] T048 [P] [US5] Extend `apps/accounts/tests/test_quick_sign_in.py` asserting `config/settings/production.py` evaluates the setting to off, and that no environment value changes that (FR-017)
- [ ] T049 [P] [US5] Extend `apps/accounts/tests/test_quick_sign_in.py` asserting the feature never authenticates an account that is not demonstration data, including when asked for one by name (FR-019)
- [ ] T050 [P] [US5] Extend `apps/accounts/tests/test_quick_sign_in.py` asserting a missing or renamed demonstration account fails visibly rather than signing someone in as whoever is nearest
- [ ] T051 [P] [US5] Write `tests/e2e/test_sign_in_visual.py` coverage asserting the customer-facing links reach the request form and the chat widget without an account

### Implementation for User Story 5

- [ ] T052 [US5] Add the quick sign-in setting to `config/settings/base.py`, defaulting to off
- [ ] T053 [US5] Force it off in `config/settings/production.py` unconditionally, not read from the environment — a single mistyped deployment variable must not put one-click administrator access on a public page
- [ ] T054 [US5] Implement the quick sign-in route in `apps/accounts/views.py`, refusing on the setting before anything else and accepting only demonstration accounts
- [ ] T055 [US5] Render the controls in `templates/accounts/sign_in.html` only when enabled, alongside links to the customer-facing screens, which have no account to sign into
- [ ] T056 [US5] Note in `docs/production-readiness.md` that this exists, that production forces it off, and which test proves it
- [ ] T057 [US5] Extract and translate this phase's strings, then check with `tools/catalog.py status`

**Checkpoint**: three roles reachable in one click where it is enabled, and unreachable by any route where it is not.

---

## Phase 8: User Story 6 - The audit log can be read (Priority: P3)

**Goal**: A reviewer can see who changed what without wading through every field of every record.

**Independent Test**: Create a ticket and change its status; find both in the log without
horizontal scrolling or internal field names.

### Tests for User Story 6

- [ ] T058 [P] [US6] Write `apps/core/tests/test_audit_readability.py` asserting a creation is presented as a creation rather than as every field changing from nothing — measured at 16 fields on a real ticket ([research.md](research.md) §8)
- [ ] T059 [P] [US6] Extend `apps/core/tests/test_audit_readability.py` asserting a change lists only the fields that moved
- [ ] T060 [P] [US6] Extend `apps/core/tests/test_audit_readability.py` asserting reverse relations — `conversations`, `inbound_logs` — are not listed as changed fields
- [ ] T061 [P] [US6] Extend `apps/core/tests/test_audit_readability.py` asserting field names are translated and no internal identifier is shown
- [ ] T062 [P] [US6] Extend `apps/core/tests/test_audit_readability.py` asserting nothing stored is altered by the rendering — entries are immutable (MVP FR-028) and this work is display only
- [ ] T063 [P] [US6] Extend `tests/e2e/test_mobile_layout.py` asserting the audit log does not scroll sideways

### Implementation for User Story 6

- [ ] T064 [US6] Present creations as creations in `apps/core/views.py` and `templates/core/audit_log.html`
- [ ] T065 [US6] Filter reverse relations and unchanged fields out of what an entry displays, in `apps/core/templatetags/`
- [ ] T066 [US6] Translate field names for display in `apps/core/templatetags/`, falling back to the stored name rather than to nothing when no translation exists
- [ ] T067 [US6] Bound what one row shows in `templates/core/audit_log.html` and `static/css/base.css`, keeping the remainder reachable — nothing may become unreadable
- [ ] T068 [US6] Extract and translate this phase's strings, then check with `tools/catalog.py status`

**Checkpoint**: the audit log is usable as evidence rather than merely complete.

---

## Phase 9: Polish & Cross-Cutting Concerns

- [ ] T069 Confirm every test in `tests/test_reported_defects.py` now passes, and that each one failed before its phase — a fix nobody saw fix anything is a claim
- [ ] T070 [P] Demonstrate each check added by this feature fails when its defect is reintroduced deliberately (FR-021) — the scope refusal, the scopeless explanation, the placeholder rule, the production gate, the audit filtering — and record what was broken and what failed in `specs/003-fix-admin-and-signin/quickstart.md`
- [ ] T071 [P] Extend `tests/test_scope_isolation.py` so the new administration routes are covered by the 404-not-403 sweep automatically
- [ ] T072 [P] Add the new screens to `tests/e2e/test_rtl_layout.py` and `tests/e2e/test_accessibility.py`
- [ ] T073 [P] Update `docs/agent-guide.md` in both languages with the first-run route and what an administrator sees when their account has no scope
- [ ] T074 Run all nine scenarios in [quickstart.md](quickstart.md) in both languages, reproducing each defect first
- [ ] T075 Confirm `tools/catalog.py status` reports `locale/ar/LC_MESSAGES/django.po` and `locale/en/LC_MESSAGES/django.po` with nothing missing, nothing fuzzy, and no placeholder mismatch

---

## Dependencies & Execution Order

### Phase order

```text
Phase 1 Setup — the five defects, reproduced as failing tests
   └─▶ Phase 2 Foundational — the placeholder rule
          │      ⚠️ blocks Phases 6 and 8: both add strings
          ├─▶ Phase 3 US1 (P1) 🎯 the reported defect — shippable alone
          ├─▶ Phase 4 US2 (P1)    independent of US1
          ├─▶ Phase 5 US3 (P2)
          │      └─▶ Phase 6 US4 (P2)   the sign-in screen adds strings
          │             └─▶ Phase 7 US5 (P3)   quick sign-in lives on that screen
          └─▶ Phase 8 US6 (P3)    adds strings; needs Phase 2 only
                 └─▶ Phase 9 Polish
```

### Hard ordering constraints

1. **Phase 2 before Phases 6 and 8.** Both add translatable strings. Adding strings under a
   check that cannot see a wrong translation is how the `Reference` entry arrived.
2. **Phase 6 before Phase 7.** Quick sign-in renders on the sign-in screen; building it before
   that screen exists means building it twice.
3. **T047 and T048 are not optional and not deferrable.** A quick sign-in route that works when
   its control is hidden is an authentication bypass, and it will pass every other test here.

### What is NOT ordered

US1 and US2 are independent of each other despite both being P1, and independent of everything
after them. Either can ship alone. US6 needs only Phase 2.

### Parallel opportunities

- Every task marked [P] within a phase touches a different file.
- US1, US2 and US6 can proceed simultaneously once Phase 2 is done.
- US3 → US4 → US5 is the one chain, and it is a chain for real reasons rather than convenience.

---

## Implementation Strategy

### Ship the reported defect first

1. Phase 1 — reproduce all five, watch them fail
2. Phase 2 — the placeholder rule
3. Phase 3 — US1
4. **Stop and validate**: quickstart scenarios 1 and 2
5. Ship. The administrator who reported this can create accounts and find them.

### Then, in order of what is still wrong

6. Phase 4 (US2) — a new installation works, and a broken administrator recovers
7. Phase 5 (US3) — the product is bilingual where it claimed to be
8. Phases 6–7 (US4, US5) — the first screen, then the testing convenience
9. Phase 8 (US6) — the audit log becomes readable
10. Phase 9 — prove every check fails when it should

### Note on Phase 9

T070 is the task most likely to be skipped, because by then everything passes and breaking it on
purpose feels like undoing finished work. It is the task this feature exists to establish. The
catalog checks passed for weeks while a heading displayed a raw placeholder, and the only thing
that would have caught it is someone deliberately writing a wrong translation to see what
happened.

---

## Notes

- [P] = different files, no dependency.
- Every phase ends with translation extraction, because a phase that adds a string and defers
  its translation is a phase that shipped an English string into an Arabic screen.
- Commit after each task or logical group.
- Stop at any checkpoint; every story is independently valuable.
