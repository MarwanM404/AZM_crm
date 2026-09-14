# Phase 0 — Research

Eight decisions. The first one decides most of the others, and it was settled by reading the
middleware rather than by preference.

---

## 1. A customer is not a `User`

**Decision**: Customers are a separate account model with their own sign-in, their own session,
and their own place on the request. `request.user` continues to mean "a member of staff" and
means nothing else.

**Rationale**: Two facts about the existing code make the alternative unsafe rather than merely
untidy.

The login middleware's rule is **"authenticated → let through"**. It checks
`request.user.is_authenticated` and nothing more. Only thirteen places in the product carry a
role check, and they are the administrator and supervisor screens; the ticket queue, the
customer list and the chat console rely on being signed in plus department scoping. So a
customer who is an authenticated `User` walks through that middleware into every one of them.

And `role` defaults to `AGENT`. A customer account created anywhere that forgets to set the
role explicitly *is* an agent — a missing keyword argument away from a breach.

Put together: making customers a role on `User` means the only thing standing between a
customer and the ticket queue is that they have no department. That is exactly what FR-028
forbids, and the specification says why — a customer looks correctly excluded whether or not
anybody implements the exclusion, so the mistake is invisible until it is not.

With a separate model, `request.user.is_authenticated` is false for a customer and every
existing staff screen refuses them without being modified. Eleven places that assume
`request.user.department` keep their assumption safely.

**Alternatives considered**: `Role.CUSTOMER` on `User`, with the middleware tightened to
"authenticated **and** staff" and a guard on every staff view. Rejected: it reuses Django's
authentication conveniently and makes one forgotten guard a data breach, on a product where
thirteen of roughly forty views currently carry a guard at all. The cost of the separate model
is a second sign-in flow; the cost of the shared model is paid the first time somebody adds a
view and forgets.

**Consequence**: the portal's authentication is built rather than inherited. Password hashing,
session handling and timing-safe comparison come from the framework; the flow around them does
not.

---

## 2. Where a customer's identity comes from

**Decision**: A confirmed email address, matched to `Contact` records by address at read time.
The account stores the address; it does not store a link to a contact.

**Rationale**: Matching at read time is what makes the edge cases behave. A customer registers
before they have written in — no contact exists yet, and the list is empty rather than broken.
An administrator later edits a contact's address — the customer's view follows the address they
proved, which is the only thing they proved. A customer has written from one address and been
recorded twice — both records match, and they see both.

Storing a link instead would fix the association at registration, which is the moment we know
least.

**Alternatives considered**: create a `Contact` at registration and link it. Rejected because it
puts a record in the customer list for somebody who has never contacted the desk, and an agent
browsing customers would see people who are not yet customers.

---

## 3. Proving the address

**Decision**: A single-use, expiring link sent to the address being claimed. Until it is
followed, the account exists and can do nothing at all.

**Rationale**: The address is the whole of the identity — it decides which tickets are shown —
so it has to be proved before anything is shown. "Exists but can do nothing" is deliberately
different from "does not exist": it lets a second registration attempt on the same address be
answered identically to the first (FR-007), which is what stops the screen becoming a way to
ask whether an address is known.

Expiry and single use are what keep a link from becoming a password that never changes — a
message in a mailbox is readable by anyone who reaches that mailbox later.

---

## 4. Not disclosing whether an address is known

**Decision**: Registration and reset answer identically for an address that has an account and
one that does not. The difference goes to the address itself, not to the screen.

**Rationale**: This is the requirement most likely to be lost to a helpful error message. "That
email is already registered" is a kindness on a consumer site and an enumeration oracle on a
support desk, where knowing an address is a customer of this company is itself worth something.

The owner still finds out: an attempt to register an address that already has an account sends
a message to that address saying so. The information reaches the person entitled to it by a
route the attacker does not control.

**What this costs**: a genuine customer who has forgotten they registered gets a message rather
than an on-screen answer. Accepted, and it is the reason the message must say clearly what to
do next.

---

## 5. Rate limiting and lockout

**Decision**: Per address and per source, on registration, sign-in, reset, confirmation, reply
and new request. Configured as settings, not constants. Lockout after a configured number of
consecutive sign-in failures, for a configured period, with the owner told.

**Rationale**: The product already has a rate-limiting dependency and already uses it, so this
adds no dependency — but the portal is the first place where the person on the other side is
unknown, so it is the first place the limits are load-bearing rather than prudent.

Per address **and** per source, because they stop different things: per address stops somebody
grinding one account, per source stops somebody sweeping many.

Settings rather than constants because the right numbers are unknown until real customers use
it, and discovering they are wrong should not need a release.

**A caution to carry into implementation**: the rate limiter's own cache leaked between tests
once already in this project, which is why `conftest.py` clears it. Tests here will need the
same discipline or they will pass and fail by ordering.

---

## 6. Replies and new requests from the portal

**Decision**: Both go through the existing ticket services rather than a parallel path. A
portal reply is an inbound message like an emailed one, and reuses the same state transitions.

**Rationale**: The behaviour the specification asks for — a reply stops a ticket waiting on the
customer, a reply to a resolved ticket reopens it — already exists for email. A second
implementation would be a second thing to keep in step, and the first divergence would be
invisible: the ticket would simply behave differently depending on where the customer typed.

The channel is recorded so an agent can see where it came from, which is a label on one code
path rather than two code paths.

---

## 7. Keeping internal messages out

**Decision**: The portal reads through the same customer-facing filter as every other
customer-facing output, and its templates join the existing sweep by directory rather than by
being listed.

**Rationale**: The boundary exists and is swept; the risk is that the portal's screens are not
in the sweep. That sweep is already self-maintaining for the directories it covers — a template
added to a covered directory fails the build until it is listed. Putting the portal's templates
in their own directory and adding that directory is a one-line change that makes every future
portal screen covered automatically.

Live chat learned this the harder way: `templates/chat/` mixes staff and customer screens, so
it cannot be swept wholesale and every template must be classified by hand. The portal is
entirely customer-facing, so it does not have that problem and should not inherit that pattern.

---

## 8. Bilingual, including email

**Decision**: The portal uses the language mechanisms the product already has. Its emails are
sent in the language of the customer's own preference, defaulting to the language they
registered in.

**Rationale**: The machinery exists — two catalogs, both domains checked, right-to-left by
logical properties, and a language switch that works before signing in (added in spec 003 for
exactly this kind of screen). The portal's sign-in, registration and reset screens are read by
people with no session, which is the case that switch was built for.

Email is the part that is easy to get wrong, because a message is composed once and read later:
the language has to come from the recipient's stored preference rather than from whatever was
active when the message was queued.

---

## Dependencies

None added. Password hashing, session handling, rate limiting and email are all already in use.

## The one thing that is not a decision

Email delivery is a precondition. `docs/email-setup.md` has not been actioned and IT controls
the mail domain. Every story here except reading a ticket depends on a message arriving:
registration cannot complete, a password cannot be reset, and a second registration attempt
cannot be reported to its owner. This is recorded here as well as in the specification because
it is the thing most likely to be discovered late.
