# Phase 1 — Data model

One new entity, one new short-lived record, and nothing changed on anything that exists. That
last part is deliberate and worth checking during review: a portal that alters `Ticket` or
`Message` is a portal that has reached further than it should.

## New

### CustomerAccount

The portal's identity. **Not** a `User`, for the reason in [research.md](research.md) §1: the
staff middleware admits anything authenticated, so a customer who were a `User` would reach
every staff screen and be saved only by having no department.

| Field | Why it exists |
|---|---|
| email | The identity. Unique, and the only thing that decides which tickets are shown |
| password | Chosen by the customer, stored so it cannot be read back |
| email_confirmed_at | Null until proved. Null means the account can do nothing at all |
| language | Their own preference, used for screens and for email composed later |
| is_active | Deactivation ends access, as it does for staff |
| created_at, updated_at | As every record here has |

**No department. No branch. No role.** Not "left empty" — absent, so there is no field for a
future change to populate and no shape a staff query could accidentally match.

**Deliberately not stored**: a link to a `Contact`. Matching happens at read time by address
(research.md §2), so a customer can register before they have ever written in, an edited
contact address does not silently move what they can see, and two contact records with the same
address both match.

### CustomerToken

A single-use, expiring link for confirming an address or resetting a password.

| Field | Why it exists |
|---|---|
| account | Who it is for |
| purpose | Confirmation or reset. A confirmation link must not reset a password |
| expires_at | A message sits in a mailbox indefinitely; the link must not |
| used_at | Null until followed. Single use is what stops a forwarded message being a key |

Stored so the value in the email cannot be recovered from the database, for the same reason the
chat visitor token is: a table of live tokens is a table of live credentials.

## Unchanged, and checked

- **Ticket**, **Message**: untouched. The portal reads them through the existing customer-facing
  filter and writes a reply through the existing ticket services. A new value on the channel
  field records where a message came from — a label, not a branch.
- **Contact**: untouched. The portal matches to it and never edits it. A customer correcting
  their own name is not in this feature.
- **User**: untouched, and this is the point of the whole design. Every staff query, every
  scoping filter, and the eleven places that assume `request.user.department` keep working
  because a customer never appears there.

## What a reviewer should check

| Claim | How to check it |
|---|---|
| A customer cannot become staff | `CustomerAccount` has no role, department or branch field |
| An unconfirmed account reaches nothing | Every read path requires `email_confirmed_at` |
| A link cannot be reused | `used_at` is set on first use and checked before every use |
| The portal does not widen the message boundary | It reads through the same filter as email |
| Nothing existing changed | The migration adds tables and one channel value, and alters no column on `Ticket`, `Message`, `Contact` or `User` |

The last row is the one to verify rather than trust. A feature that says it changes nothing and
adds an `AlterField` has changed something.
