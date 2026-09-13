# Phase 0 — Research

Eight decisions. Each was checked against the running code rather than reasoned from the
framework's documentation, because three of the five defects exist precisely where the code and
the reasonable assumption diverge.

---

## 1. Refusing an out-of-scope account, rather than silently correcting it

**Decision**: The department and branch fields default to the acting administrator's own. A
submission naming any other scope is refused with a message, not quietly rewritten.

**Rationale**: Two failures are possible and only one is visible. Silently rewriting the scope
would give a second invisible outcome — the administrator asked for Billing, got Support, and
is told nothing — which is the same defect wearing different clothes (FR-020). Refusing costs
one round trip and says what happened.

Restricting the dropdown to a single option was considered and rejected: a control with one
choice teaches an administrator that scope is not a real field, and the moment a second branch
exists the lesson is wrong. The field stays visible and explains itself.

**Alternatives considered**: allow any scope and show created accounts from every department in
the list. Rejected — it would make the administration screen the one place where FR-023 does
not apply, and MVP FR-023 makes no exception for role.

---

## 2. The scopeless administrator: bootstrap and recovery

**Decision**: Three layers, because no single one covers the case.

1. **Prevent**: the account-creation path refuses to produce a staff account without a scope.
2. **Bootstrap**: a dedicated first-run command creates the first administrator *with* a
   department and branch, creating them if the installation has none.
3. **Recover**: an administrator whose own account has no scope is told so on every scoped
   screen, and can set their own scope — the only self-service scope change in the product.

**Rationale**: `REQUIRED_FIELDS = ["full_name"]`, so the framework's own account-creation
command asks for an email and a name and nothing else. Adding the scope fields there was
considered and rejected on a practical point: on a fresh installation there are no departments
to choose from, so the prompt would ask for a foreign key that cannot yet exist. A command that
creates the scope and the administrator together is the only order that works.

Layer 3 is the uncomfortable one, and it needs stating plainly: it lets an administrator change
their own scope, which everywhere else in this product is forbidden. It is allowed only when
the account has *no* scope — a state from which the administrator can otherwise see nothing and
no screen can help them. An administrator who already has a scope cannot change it, and the
edge case in the spec is exactly why: with one administrator and no scope, requiring a second
administrator to fix it makes a new installation unrecoverable from its own first screen.

**Alternatives considered**: treating a scopeless account as "sees everything". Rejected
outright — it inverts deny-by-default (Constitution III) and turns a misconfiguration into a
privilege escalation.

---

## 3. Client-side translations

**Decision**: Serve the framework's JavaScript translation catalog for the active language and
let the existing `gettextOrFallback` helper find a real `gettext`. No new dependency.

**Rationale**: The helper already exists and already falls back correctly; what is missing is
the catalog it looks for, which was never routed. This is a wiring gap, not a design gap, and
the fix is two lines plus a test that the helper stops taking the fallback.

The catalog must be served per-language and must not be cached across languages — an Arabic
agent receiving the English catalog is the same defect in a new place. The check is that the
client's strings change when the language does, not merely that the catalog loads.

**Alternatives considered**: passing translated strings into the page as data attributes.
Rejected — it puts each string in two places, and the second place is the one nobody remembers
to update.

---

## 4. Detecting a wrong translation

**Decision**: One precise rule, enforced automatically — a translation may not contain a format
placeholder that its source string does not contain. Plus a recorded human review step for
everything the rule cannot see.

**Rationale**: Scanning both catalogs with this rule found exactly one offender (the `Reference`
entry that renders `رد: %(REFERENCE)S`) and no false positives. Arabic's zero, one and two
plural forms legitimately *omit* a numeral the source has, so the reverse rule — requiring every
source placeholder in the translation — would fire on five correct entries. The asymmetry is
the whole finding: an extra placeholder is always a bug, a missing one often is not.

The limit is stated rather than engineered around. A fluent Arabic sentence with the wrong
meaning passes this rule, and nothing automatic will catch it. Pretending otherwise would
repeat the mistake that produced the defect — a check that reported correctness when it had
only measured presence (FR-021).

**Alternatives considered**: comparing translation length ratios, or round-tripping through a
translation service. Rejected as unreliable, and the second sends customer-facing strings to a
third party for no gain.

---

## 5. Bilingual department and branch names

**Decision**: Both models already carry a second name. Reading the right one becomes a property
on the model, used everywhere the name is displayed, rather than a template-level choice.

**Rationale**: The field exists and is unused, which means every display site currently makes
the same wrong choice independently. One property makes the choice once. Where the second name
is blank, the first is shown — a missing translation should degrade to a readable name, not to
an empty cell.

---

## 6. Choosing a language before signing in

**Decision**: Anonymous language selection uses the framework's own language-cookie mechanism,
separate from the existing signed-in switcher. On a successful sign-in, a language chosen while
signed out is adopted as that account's preference.

**Rationale**: The existing switcher writes `request.user.language`, so it requires an account
and cannot serve the sign-in screen at all. The framework's cookie mechanism is read by the
locale middleware for anonymous requests and needs no new storage.

The adoption step at sign-in is what makes FR-014 real, and it resolves a live inconsistency
worth recording: a signed-in account defaults to Arabic, while an anonymous visitor defaults to
English. Someone who deliberately picked a language on the way in should not have it changed
under them one page later.

**Out of scope, deliberately**: whether an anonymous visitor with no stated preference should
default to Arabic rather than English. That is a product decision about the public request form
as much as this screen, and it is not a defect.

---

## 7. Gating quick sign-in

**Decision**: An explicit setting, off by default, which the production configuration sets off
unconditionally rather than reading from the environment. Three tests: the control is absent
when disabled; a direct request is refused when disabled; and the production configuration
evaluates to off.

**Rationale**: This is the one part of the feature that can cause harm, so the gate is designed
around the failure rather than the feature. Reading the flag from the environment in production
would mean a single mistyped deployment variable turns a public page into one-click
administrator access. Hard-coding it off there removes that path entirely, which costs nothing:
nobody wants this on a production deployment, so there is no flexibility being given up.

The second test matters as much as the first and is easy to skip. Hiding a button does not
disable the route behind it, and a route that works when its control is hidden is a route
someone will find.

Accounts offered are the demonstration accounts only, whose passwords are already in this
repository. That is what makes the feature safe to *have* — it discloses nothing not already
disclosed. Pointed at a real account it would be an authentication bypass, which is why FR-019
forbids it rather than discouraging it.

**Alternatives considered**: enabling it wherever debugging is on. Rejected because that
conflates two decisions — a deployment can have debugging on for a day without anyone meaning
to publish one-click administrator access.

---

## 8. Making the audit log readable

**Decision**: Show a creation as a creation. For a change, list only the fields that moved.
Exclude reverse relations. Show field names in the reader's language. Cap what one row displays,
with the rest reachable.

**Rationale**: Measured on a real entry rather than assumed. A ticket creation records **16
fields**, all as "nothing → value", and among them are reverse relations — `conversations`,
`inbound_logs` — which are not fields anyone edited and mean nothing to a reader. The library's
own display helper improves some names (`created at`, `ID`) but still returns all sixteen and
still includes the relations, so adopting it is a partial fix at best and it was worth checking
before planning around it.

Nothing about the stored entries changes. They are immutable by requirement (MVP FR-028) and
this work is display only — which also means it cannot lose information: everything currently
shown remains reachable.

---

## Dependencies

None added. Every decision above uses the framework already in use or code already present,
which is the answer Constitution IV asks for.
