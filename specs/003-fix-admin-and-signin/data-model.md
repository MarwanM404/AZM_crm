# Phase 1 — Data model

Almost nothing changes. This is a defect feature: four of the five findings are about what the
system *shows*, not what it stores, and the fifth is about a value being absent rather than a
field being missing.

Recording that explicitly matters, because the temptation in a defect feature is to add a
column per symptom.

## Unchanged

- **Staff account**: already carries a role, a department and a branch. The defect is that the
  last two can be empty and that nothing notices. No new field — a constraint and a bootstrap
  path, not a column.
- **Department**, **Branch**: already carry a name in each language. The second name is stored
  and never read. No new field — a read path.
- **Audit entry**: immutable by requirement (MVP FR-028) and unchanged by this work. Every fix
  here is in the rendering. Nothing stored is altered, added or removed.
- **Translation catalogs**: data files, not database state. A new check reads them.

## Changed

### Staff account — scope becomes required in practice

`department` and `branch` are nullable today, and the null case is what User Story 2 is about.

They stay nullable. Making them non-null would be the obvious move and it is wrong here for two
reasons. Existing scopeless accounts — the very administrator reporting this defect — would
block the migration, and a required field cannot express "this account is broken and here is how
to fix it", which is what FR-004 and FR-005 ask for. The rule is enforced at every creation
path instead, and the null state is handled as a recoverable condition rather than made
unrepresentable.

**Validation**: no staff account may be created without a department and a branch, by any route.
**Existing rows**: an account already lacking a scope stays readable and can set its own, once.

### A new setting: whether quick sign-in exists

Configuration, not stored data. Off by default; forced off in the production configuration
rather than read from the environment there. It has one legitimate value in a real deployment,
so it is not a switch anyone will want to change.

## Entity notes for implementation

| Entity | What the feature needs of it |
|---|---|
| Staff account | A scope defaulted from the acting administrator; a scopeless state that explains itself; one self-service scope change, only from nothing |
| Department, Branch | The name in the reader's language, falling back to the other when blank |
| Demonstration account | Identifiable as demonstration data, so quick sign-in can offer those and only those |
| Audit entry | Creations distinguishable from changes; reverse relations distinguishable from fields |

The last row is the one worth checking during the plan: "distinguishable" must be decidable from
the stored entry, not inferred from how it looks.
