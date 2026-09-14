# Contract: HTTP endpoints

Every portal route. The staff surface is unchanged and no staff route appears here, which is
itself the contract: this feature adds a second front door and does not widen the first.

## Reachable without a session

These are new exemptions to the deny-by-default rule, and each needs the written justification
the existing guard demands.

| Method | Path | Purpose | Requirement |
|---|---|---|---|
| GET, POST | `/portal/register/` | Create an account | FR-001 |
| GET | `/portal/confirm/<link>/` | Prove the address | FR-002, FR-004 |
| GET, POST | `/portal/sign-in/` | Sign in | FR-001 |
| GET, POST | `/portal/reset/` | Ask for a reset | FR-007 |
| GET, POST | `/portal/reset/<link>/` | Choose a new password | FR-012 |

## Requires a confirmed customer

| Method | Path | Purpose | Requirement |
|---|---|---|---|
| GET | `/portal/` | Their requests: reference, subject, status, dates | FR-013, FR-014 |
| GET | `/portal/requests/<reference>/` | One request and its customer-facing conversation | FR-015, FR-016 |
| POST | `/portal/requests/<reference>/reply/` | Reply | FR-020 – FR-022 |
| GET, POST | `/portal/requests/new/` | Raise a request | FR-023 |
| POST | `/portal/sign-out/` | End the session | — |

## Refusals

| Condition | Response | Requirement |
|---|---|---|
| A request that is not this customer's | Not found — never forbidden | FR-017 |
| Any portal route, account unconfirmed | Refused, saying the address is unconfirmed | FR-002 |
| Any portal route, no customer session | Sent to portal sign-in, never to staff sign-in | FR-026 |
| Any **staff** route, customer session | Refused as if not signed in | FR-026, FR-028 |
| Any portal route, **staff** session | Refused: staff are not customers of their own desk | FR-030 |
| Registration with an address that has an account | Identical to a first registration; the address is told | FR-007, FR-008 |
| Reset for an address with no account | Identical to one that has | FR-007 |
| A link that is expired or already used | Refused, with a way to request another | FR-004 |
| Any of these beyond its configured limit | Refused, saying when to try again | FR-010, FR-011 |

## Invariants every contract test asserts

1. A customer session reaches **no** staff route — enumerated from the URL configuration, not
   from a list somebody maintains, so a route added later is covered on the day it is added.
2. That refusal holds when the customer's account has a department forced onto it by other
   means: the refusal rests on being a customer, not on having no scope (FR-028).
3. An unconfirmed account reaches no portal route that reads or writes anything.
4. No portal response, in either language, contains an internal message.
5. A request that is not the customer's is refused identically to one that does not exist —
   same status, same body.
6. Registration responses for a known and an unknown address are byte-identical.
7. A confirmation link works once and a reset link works once.
8. A reply from the portal produces the same ticket state change as an emailed reply.
