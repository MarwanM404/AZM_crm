# Contract: HTTP endpoints

Only the surfaces this feature changes or adds. Everything else in the product is untouched.

## Changed

| Method | Path | Who | Change | Requirement |
|---|---|---|---|---|
| GET | `/admin/users/new/` | administrator | Department and branch default to the acting administrator's own | FR-001 |
| POST | `/admin/users/new/` | administrator | Refused with a reason when the named scope is not the administrator's | FR-002 |
| GET | `/admin/users/` | administrator | A newly created account is identifiable; a scopeless administrator is told why the list is nearly empty | FR-003, FR-004 |
| GET | `/tickets/`, `/customers/`, `/chat/console/`, `/chat/supervise/` | any staff | An empty result caused by the viewer having no scope is explained as that, not as no data | FR-004 |
| GET | `/admin/audit/` | administrator | Creations shown as creations; only changed fields listed; field names translated; row height bounded | FR-022 – FR-025 |
| GET | `/sign-in/` | anyone | Carries the product's chrome; offers a language switch; offers quick sign-in only when enabled | FR-012, FR-013, FR-015 |

## Added

| Method | Path | Who | Purpose | Requirement |
|---|---|---|---|---|
| POST | `/language/anonymous/` | anyone, signed out | Choose a language before signing in | FR-012 |
| GET | `/jsi18n/` | anyone | Client-side translation catalog for the active language | FR-007, FR-011 |
| POST | `/sign-in/as/<role>/` | anyone, **only when enabled** | Sign in as a demonstration account | FR-015 |

## Refusals

| Condition | Response | Requirement |
|---|---|---|
| Account creation names a scope the administrator does not administer | Refused, explaining the account would not be visible to them | FR-002 |
| Account creation omits a department or branch | Refused | FR-006 |
| Quick sign-in requested while disabled | Refused, whether or not a control was rendered | FR-017, FR-018 |
| Quick sign-in requested for an account that is not demonstration data | Refused | FR-019 |
| Quick sign-in under production configuration | Refused unconditionally | FR-017 |
| Anonymous language choice names an unsupported language | Refused | FR-012 |

## Invariants every contract test asserts

1. A quick sign-in route refuses when the feature is disabled, **called directly**, with no
   control rendered anywhere. Hiding a control is not disabling a route.
2. The production configuration evaluates the quick sign-in setting to off, and no environment
   value changes that.
3. Quick sign-in never authenticates an account that is not demonstration data.
4. An account creation that succeeds is followed by that account being visible to its creator.
5. An account creation that would not be visible does not happen at all.
6. The client-side catalog served for Arabic differs from the one served for English — serving
   a catalog is not the same as serving the right one.
7. No response body, in either language, contains a format placeholder.
