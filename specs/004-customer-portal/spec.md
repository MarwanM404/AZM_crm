# Feature Specification: The customer portal

**Feature Branch**: `004-customer-portal`

**Created**: 2026-09-14

**Status**: Draft

**Input**: Customers create an account, sign in, and manage their own support requests. Decisions taken by the product owner on 2026-09-14: email and password; read, reply and open new tickets; a customer sees the tickets of their own verified email address and nothing else.

## Context

This is the portal phase that the first three specifications deferred to. Both record the same
assumption in the same words — *visitors are anonymous: there is no customer login until the
portal phase* — and live chat states plainly that an email address typed into a form is not
proof of identity, so a visitor must not be able to reach an existing ticket by naming one.

**This specification is what changes that, and the change has to be deliberate.** Everything
built so far has one authorization model: what you may see is decided by the department and
branch on your account. A customer has neither. The account that specification 003 described
as blind — no department, no branch, sees nothing — is structurally the same shape as a
customer account, and the distance between "sees nothing" and "sees the ticket queue" must not
be that a customer happens to have no scope. It must be that a customer is not staff, checked
as its own fact.

The other change is quieter and larger in consequence. Until now every account in this product
was created by an administrator, has a password an administrator set, and cannot reset it. A
portal adds self-service registration, an email that must be proved, a password the customer
chooses, a reset flow, and a lockout — five security surfaces the product does not have today,
each of which is a way in.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A customer signs up and proves who they are (Priority: P1)

Someone who has written to support creates an account with their email address and a password,
confirms the address from a message sent to it, and is then signed in.

**Why this priority**: Nothing else in this feature can exist before identity does. Every other
story reads or writes a customer's own data, and "their own" has no meaning until an address is
proved. It is also the story that carries the most risk: the registration screen is public, and
it is the only screen in this product that creates an account.

**Independent Test**: Register with an address, confirm from the message, and sign in. Then
attempt each step out of order and confirm each is refused.

**Acceptance Scenarios**:

1. **Given** a person with no account, **When** they register with an email address and a
   password, **Then** an account is created that cannot yet be used, and a confirmation is sent
   to that address.
2. **Given** they have registered, **When** they follow the confirmation, **Then** the address
   is proved and they can sign in.
3. **Given** they have registered and not confirmed, **When** they try to sign in, **Then** they
   cannot, and they are told the address is unconfirmed rather than that the password is wrong.
4. **Given** an address that already has an account, **When** somebody registers it again,
   **Then** the response is indistinguishable from a first registration, and the owner of the
   address is told an attempt was made.
5. **Given** an address that already has tickets, **When** somebody registers it, **Then**
   nothing about those tickets is disclosed until the address is confirmed.
6. **Given** an address with no history at all, **When** somebody registers it, **Then** the
   account is created: a customer exists before their first ticket does.
7. **Given** a confirmation has been used, **When** it is followed again, **Then** it does not
   work a second time.
8. **Given** a confirmation was issued some time ago, **When** it is followed after it expires,
   **Then** it does not work, and a new one can be requested.
9. **Given** repeated registration attempts from one source, **When** they exceed the
   configured limit, **Then** they are refused.

---

### User Story 2 - A customer sees their own requests (Priority: P1)

A signed-in customer sees the requests they have raised — reference, subject, status, when it
was opened, when it last moved — and opens one to read the conversation.

**Why this priority**: It is the thing a customer actually wants, and the reason the portal
exists: answering "what is happening with my request" without writing in to ask. Equal to
Story 1 because together they are the smallest portal worth having.

**Independent Test**: Sign in as a customer with tickets and confirm the list shows theirs and
only theirs; attempt to open somebody else's and confirm it is not found.

**Acceptance Scenarios**:

1. **Given** a signed-in customer, **When** they open the portal, **Then** they see the requests
   raised from their confirmed address, with reference, subject, status and dates.
2. **Given** a customer with no requests, **When** they open the portal, **Then** they are told
   there is nothing yet, and how to raise one.
3. **Given** a request of theirs, **When** they open it, **Then** they see the conversation as
   the customer side of it — every message sent to or from them, in order.
4. **Given** a request of theirs carrying an internal note, **When** they open it, **Then** the
   note does not appear, in any form, anywhere on the page.
5. **Given** a request belonging to somebody else, **When** they try to open it by its
   reference, **Then** it is not found — not forbidden, because a refusal that distinguishes
   them is a way to learn which references exist.
6. **Given** a colleague at the same organization has requests, **When** the customer looks,
   **Then** they do not see them: the portal shows the requests of an address, not of a company.
7. **Given** a request that has been resolved or closed, **When** they look, **Then** they can
   still read it.

---

### User Story 3 - A customer replies to a request (Priority: P2)

A customer adds to a conversation from the portal rather than by email, and the agent sees it
on the ticket like any other reply.

**Why this priority**: It closes the loop — without it the portal is somewhere to look, and the
customer still has to leave it to say anything. Below the first two because a portal that only
shows is already useful, and this one opens a new door into the system for text a stranger
wrote.

**Independent Test**: Reply from the portal and confirm it appears on the ticket for the agent,
attributed to the customer, and that the ticket's state responds as it does to an emailed reply.

**Acceptance Scenarios**:

1. **Given** a signed-in customer viewing their request, **When** they reply, **Then** the reply
   joins the conversation and is visible to the agent on that ticket.
2. **Given** they reply, **When** the agent sees it, **Then** it is attributed to the customer
   and marked as having come from the portal, not from email.
3. **Given** a request awaiting the customer, **When** they reply, **Then** the request stops
   waiting on them, exactly as an emailed reply does.
4. **Given** a request that is resolved, **When** the customer replies, **Then** it reopens, as
   an emailed reply reopens it.
5. **Given** a customer replying repeatedly, **When** they exceed the configured limit,
   **Then** they are refused, told when they may try again, and nothing they wrote is lost.
6. **Given** an empty or over-long reply, **When** they send it, **Then** it is refused with a
   reason, and nothing is added to the conversation.
7. **Given** a request belonging to somebody else, **When** a reply is directed at it, **Then**
   it is refused as not found and nothing is written.

---

### User Story 4 - A customer raises a new request (Priority: P2)

A signed-in customer opens a new request from the portal, without retyping who they are.

**Why this priority**: The public request form already exists and works for anonymous people.
This is the same act with identity already established, which is a smaller improvement than
Stories 1 to 3 — but leaving it out means a signed-in customer has to use a form that asks them
for a name and an email the system already knows.

**Independent Test**: Raise a request from the portal, confirm it appears in the customer's own
list immediately and reaches the agent queue like any other.

**Acceptance Scenarios**:

1. **Given** a signed-in customer, **When** they raise a request, **Then** they are not asked
   for their name or email address.
2. **Given** they raise one, **When** it is created, **Then** it is attached to their contact
   record and appears in their list at once.
3. **Given** they raise one, **When** an agent looks at the queue, **Then** it is there like any
   other request, marked as having come from the portal.
4. **Given** an anonymous visitor, **When** they use the public request form, **Then** it works
   exactly as it does today: the portal adds a second path and does not change the first.
5. **Given** a customer raising requests repeatedly, **When** they exceed the configured
   limit, **Then** they are refused and told when they may try again.

---

### User Story 5 - A customer recovers a forgotten password (Priority: P2)

A customer who cannot sign in asks for a reset, follows a message sent to their address, and
chooses a new password.

**Why this priority**: A password nobody can reset becomes a support request, which is the
opposite of what a portal is for. Below the stories that deliver value because it is a path
people take rarely — but it is the second most attacked screen in any product that has one.

**Independent Test**: Request a reset, follow it, sign in with the new password, and confirm
the old one no longer works and the link cannot be reused.

**Acceptance Scenarios**:

1. **Given** a customer with an account, **When** they ask for a reset, **Then** a message is
   sent to their address carrying a link that works once.
2. **Given** an address with no account, **When** somebody asks for a reset, **Then** the
   response is identical to the case where there is one: whether an address has an account is
   not something the screen may reveal.
3. **Given** a reset has been used, **When** it is followed again, **Then** it does not work.
4. **Given** a reset was issued some time ago, **When** it is followed after it expires,
   **Then** it does not work.
5. **Given** a reset completes, **When** it does, **Then** the previous password no longer
   works and any other signed-in session for that account ends.
6. **Given** repeated reset requests for one address, **When** they exceed the configured
   limit, **Then** they are refused — and the refusal looks the same whether or not the address
   has an account.
7. **Given** repeated failed sign-ins for one account, **When** they exceed the configured
   number, **Then** further attempts are refused for the configured period, and the owner of
   the address is told.

---

### User Story 6 - A customer is not staff, and cannot become staff (Priority: P1)

A customer account reaches the portal and nothing else. No staff screen, no other customer's
data, no department, no branch.

**Why this priority**: Equal to Story 1, and the only story here whose failure is a breach
rather than an inconvenience. This product's entire authorization model is the department and
branch on an account; this feature introduces accounts that have neither, and the reason a
customer cannot see the ticket queue must be that they are a customer — not that they happen to
have no scope.

**Independent Test**: Sign in as a customer and attempt every staff route, including by typing
the address directly, and confirm each is refused.

**Acceptance Scenarios**:

1. **Given** a signed-in customer, **When** they request any staff screen, **Then** it is
   refused, whether or not a link to it was ever shown.
2. **Given** a signed-in customer, **When** they request a staff action directly, **Then** it is
   refused.
3. **Given** a customer account, **When** it is examined, **Then** it holds no department and no
   branch, and there is no route by which it can acquire one.
4. **Given** a staff account, **When** it reaches the portal, **Then** the portal does not treat
   it as a customer: a member of staff is not a customer of the desk they work at.
5. **Given** the self-service scope recovery added for administrators, **When** a customer
   account reaches it, **Then** it is refused — an account without a scope is not necessarily
   an administrator who needs one.
6. **Given** any new staff screen added in future, **When** it is added, **Then** it is covered
   by the refusal above without anybody remembering to add it.

---

### Edge Cases

- What happens when a customer registers an address that a member of staff also uses? Staff and
  customers are different kinds of account, and one address must not silently become both.
- What happens when a customer's address matches several contact records, or none? Matching is
  by address; a customer with no contact record yet has an empty list, not an error.
- What happens when an administrator changes the email on a contact record after a customer has
  confirmed it? The customer must not silently gain or lose sight of requests; the address they
  proved is the one that decides.
- What happens when a customer replies to a request that was merged or re-pointed at another
  ticket? They follow the ticket, since that is where their words went.
- What happens when a customer account is created for an address that later turns out to belong
  to somebody else — a shared or role address such as `accounts@`? Confirmation proves control
  of the address, not that the holder is the person who wrote in; this limit is real and is
  recorded rather than solved.
- What happens to a customer session when their account is deactivated? It ends, as a staff
  session does.
- What happens when confirmation email cannot be delivered at all? Registration must not appear
  to have succeeded in a way that leaves somebody waiting for a message that will never arrive.

## Requirements *(mandatory)*

### Identity

- **FR-001**: System MUST let a person register with an email address and a password of their
  choosing.
- **FR-002**: System MUST require the address to be confirmed before the account can be used
  for anything at all.
- **FR-003**: System MUST send confirmation to the address being claimed, and only there.
- **FR-004**: System MUST make a confirmation usable once, and MUST stop it working after a
  configured period.
- **FR-005**: System MUST enforce a minimum password strength and MUST refuse a password known
  to be common.
- **FR-006**: System MUST store passwords such that they cannot be recovered from storage.
- **FR-007**: System MUST respond identically whether or not an address already has an account,
  on registration and on reset.
- **FR-008**: System MUST tell the owner of an address when somebody attempts to register it
  again.
- **FR-009**: System MUST allow registration of an address that has no history in the system.
- **FR-010**: System MUST limit registration, sign-in, reset and confirmation attempts, per
  address and per source, to a configured number within a configured period, and MUST refuse
  attempts beyond it. Both numbers are settings so they can be tuned without a release; each
  screen states which limit applies to it.
- **FR-011**: System MUST refuse further sign-in attempts for an account after a configured
  number of consecutive failures, for a configured period, and MUST tell the owner of the
  address that it happened.
- **FR-012**: System MUST end other sessions for an account when its password changes.

### What a customer may see

- **FR-013**: System MUST show a customer the requests raised from the address they confirmed,
  and no others.
- **FR-014**: System MUST show, for each, its reference, subject, status, when it was opened and
  when it last changed.
- **FR-015**: System MUST show the customer-facing conversation on a request, in order.
- **FR-016**: System MUST NOT show an internal message in the portal, in any form, on any screen.
- **FR-017**: System MUST refuse a request that is not the customer's as not-found, never as
  forbidden.
- **FR-018**: System MUST NOT show a customer the requests of others at their organization.
- **FR-019**: System MUST keep resolved and closed requests readable.

### What a customer may do

- **FR-020**: System MUST let a customer reply to their own request, and MUST place the reply on
  that request as customer-authored.
- **FR-021**: System MUST record that a reply or request came from the portal rather than another
  channel.
- **FR-022**: System MUST apply to a portal reply the same effect on a request's state that an
  emailed reply has.
- **FR-023**: System MUST let a signed-in customer raise a new request without re-entering their
  identity.
- **FR-024**: System MUST validate customer-authored content on entry against a stated maximum
  length, and MUST refuse empty or over-long content with a reason that says which.
- **FR-025**: System MUST leave the anonymous request form working exactly as it does now.

### A customer is not staff

- **FR-026**: System MUST refuse every staff screen and staff action to a customer account,
  whether or not a link was shown.
- **FR-027**: System MUST NOT give a customer account a department or a branch, and MUST provide
  no route by which one can be acquired.
- **FR-028**: System MUST base that refusal on the account being a customer, not on it having no
  scope.
- **FR-029**: System MUST apply the refusal to staff screens added in future without requiring
  them to be listed.
- **FR-030**: System MUST NOT treat a staff account as a portal customer.
- **FR-031**: System MUST end a customer's session when their account is deactivated.
- **FR-032**: System MUST keep one email address from being both a staff account and a customer
  account. The edge case names the risk; this is the requirement behind it. Which way the
  refusal falls is a decision for the plan, but the two must not silently coexist, because an
  address that is both is an address whose session type decides what it can see.

### Everything else this product already promises

- **FR-033**: System MUST present every portal screen and every message it sends in the reader's
  language, Arabic or English, laid out accordingly.
- **FR-034**: System MUST record portal account creation, confirmation, sign-in failure,
  password change and customer-authored content in the audit trail.
- **FR-035**: System MUST include every portal screen in the sweep that proves no customer-facing
  output can carry an internal message, without that screen having to be listed by hand.
- **FR-036**: System MUST justify in writing each new screen reachable without a session, as the
  existing deny-by-default rule requires.

### The themes carried forward

- **FR-037**: System MUST NOT complete an action whose result the acting person cannot then see,
  without telling them at the time.
- **FR-038**: Every check introduced by this feature MUST be demonstrated to fail when the
  defect it guards against is reintroduced deliberately.

## Key Entities

- **Customer account**: an email address, a password, and whether the address has been
  confirmed. Distinct in kind from a staff account: no department, no branch, no role in the
  staff role set. The distinction is the security boundary of this feature.
- **Contact**: the existing record of a person who has written in. A confirmed customer account
  is matched to one by address; a customer may exist before a contact does.
- **Ticket**: unchanged. The portal is a second way to read and add to one.
- **Message**: unchanged, including its public and internal distinction, which the portal reads
  and never widens.
- **Confirmation and reset links**: each sent to one address, usable once, and expiring.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A customer can go from no account to reading their requests in under three
  minutes, including confirming their address.
- **SC-002**: A customer sees 100% of the requests raised from their confirmed address and 0%
  of any others, including by direct reference.
- **SC-003**: No portal screen, in either language, displays an internal message or any part of
  one.
- **SC-004**: Every staff screen and staff action refuses a customer account, verified by
  enumerating the routes rather than by a list somebody maintains.
- **SC-005**: An unconfirmed account reaches nothing.
- **SC-006**: Registration and reset responses are identical for addresses that exist and
  addresses that do not, measured by comparing the responses.
- **SC-007**: A reply sent from the portal reaches the agent's view of the ticket within the
  time an emailed reply takes, and changes the request's state identically.
- **SC-008**: Every portal screen and message reads correctly in Arabic, right to left, with no
  untranslated text and no placeholder codes.
- **SC-009**: Requests whose subject is only a status enquiry fall by at least a quarter in the
  three months after release, measured against the three months before it. This is the outcome
  the portal exists for, and it is the one criterion here that cannot be verified on the day it
  ships — which is a reason to record the baseline before release, not a reason to drop it.

## Assumptions

- Email is reliable enough to carry confirmations and resets. This is a real dependency and it
  is not yet proven in this deployment: the mail domain is controlled by IT and
  docs/email-setup.md has not yet been actioned. A portal whose confirmations do not arrive is
  a portal nobody can use, so this is a precondition for release rather than a detail.
- Customers are matched to their history by email address alone. A customer who has written in
  from two addresses sees two separate histories, and that is accepted rather than solved.
- Confirming an address proves control of the address, not the identity of the person holding
  it. A shared or role address is therefore as trustworthy as the people who can read it. This
  is the known limit of email-based identity and is recorded rather than designed around.
- The portal serves individuals, not organizations. An organization-wide view is a later
  decision and is deliberately excluded, because it means one customer reading another
  employee's support conversation.
- Staff accounts are unchanged by this feature. They keep being created by an administrator,
  with no self-service registration and no self-service reset; nothing here should be read as
  extending those to staff.
- Two-factor authentication is out of scope. It is the obvious next question for a product that
  has just grown a public sign-in, and it belongs in its own decision rather than smuggled in
  here.
- The portal is a web interface, on the same site. There is no separate application and no
  public interface for other systems to use.
