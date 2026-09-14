# Specification Quality Checklist: The customer portal

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-14
**Feature**: [spec.md](../spec.md)

## Content Quality

- [X] No implementation details (languages, frameworks, APIs)
- [X] Focused on user value and business needs
- [X] Written for non-technical stakeholders
- [X] All mandatory sections completed

## Requirement Completeness

- [X] No [NEEDS CLARIFICATION] markers remain
- [X] Requirements are testable and unambiguous
- [X] Success criteria are measurable
- [X] Success criteria are technology-agnostic
- [X] All acceptance scenarios are defined
- [X] Edge cases are identified
- [X] Scope is clearly bounded
- [X] Dependencies and assumptions identified

## Feature Readiness

- [X] All functional requirements have clear acceptance criteria
- [X] User scenarios cover primary flows
- [X] Feature meets measurable outcomes defined in Success Criteria
- [X] No implementation details leak into specification

## Notes

### What validation actually found

Three passes. The first scan for implementation detail came back clean, which was not the
useful part — the real problems were requirements that read like requirements and could not be
failed.

**Pass 1 — untestable requirements, five instances, all the same word.** "A reasonable rate"
appeared in the rate-limiting requirement and four acceptance scenarios, and "a reasonable
number" in the lockout. Reasonable to whom, measured how? A requirement nobody can fail is a
paragraph. Each now names a configured limit over a configured period, per address and per
source, with the screens saying which limit applies to them.

**Pass 2 — one success criterion was not a measurement.** SC-009 said status-enquiry support
requests would "fall measurably". It now names a quarter, over three months, against the three
months before release — and says plainly that it is the one criterion here that cannot be
checked on the day it ships, which is a reason to record the baseline beforehand rather than a
reason to drop it.

**Pass 3 — one edge case had no requirement behind it.** The edge cases ask what happens when
an address belongs to both a member of staff and a customer, and nothing required an answer.
FR-032 now does. Which way the refusal falls is left to the plan; that the two must not
silently coexist is not, because an address that is both is an address whose session type
decides what it can see.

Also corrected: "token" in Key Entities became "link". It is our word for the mechanism, not
the reader's word for the thing.

### Deliberate choices a reviewer should check rather than assume

- **Three product decisions were taken before this was written** and are recorded as
  requirements rather than presented as open: email and password rather than a link; full
  self-service rather than read-only; the customer's own address rather than their
  organization. Each of the alternatives was costed at the time and each is recoverable later —
  but a reviewer should know they were decisions, not defaults.
- **Story 6 has no user-facing value and is P1 anyway.** "A customer is not staff" delivers
  nothing a customer would notice. It is the only story here whose failure is a breach rather
  than an inconvenience, and it is P1 for that reason alone.
- **FR-028 is the sharpest requirement in the document** and the easiest to satisfy
  accidentally. A customer account has no department, and specification 003 established that an
  account with no department sees nothing — so a customer will appear to be correctly excluded
  from the ticket queue whether or not anybody implements this. The requirement is that the
  refusal rests on the account being a customer, because the other reason is a coincidence of
  two features and coincidences do not survive refactoring.

### Known limits, stated rather than designed around

Confirming an address proves control of that address. It does not prove the holder is the
person who wrote in, and a shared or role address (`accounts@`, `info@`) is therefore exactly
as trustworthy as everyone who can read it. This is the limit of email-based identity and it is
recorded in Assumptions rather than solved, because solving it means identity documents.

Email delivery is a precondition, not a detail. The mail domain is controlled by IT and
`docs/email-setup.md` has not been actioned. A portal whose confirmations never arrive is a
portal nobody can use — this feature cannot be released before that is.
