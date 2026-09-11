# Contract: Email in and out

**Date**: 2026-09-11 | **Plan**: [../plan.md](../plan.md)

Email is the MVP's only outbound customer channel and one of its two intake channels. Each rule
below is a contract test.

## Outbound

### Intake confirmation
**Trigger**: an accepted public form submission (FR-004).
**To**: the submitting contact's email.
**Language**: the language the visitor used on the form; Arabic when unknown (FR-035).
**Must contain**: the ticket reference, and a reply-to address carrying that reference.
**Must not contain**: any other customer's data, internal messages, or staff names not involved.

### Agent reply
**Trigger**: an agent sends a public message on a ticket (FR-012).
**To**: the ticket's contact.
**Language**: the contact's recorded preferred language, falling back to the language they wrote in.
**Must contain**: the agent's message body and the ticket reference.
**Must not contain**: any message with `visibility=INTERNAL`, including in quoted history (FR-015).

### Delivery outcome
- A send is queued, not performed inside the web request (FR-016).
- Retries use backoff. Permanent failure sets `delivery_status=FAILED` and records the error.
- A failure is visible to the agent on the ticket. The message remains on the thread; it is never
  silently discarded (FR-016, spec edge case).

## Inbound

### Threading rules, in priority order
1. **Reply-to token**: the recipient address matches `support+<reference>@<domain>` → attach to that
   ticket.
2. **Headers**: `In-Reply-To` or `References` matches a known outbound message `external_id` →
   attach to that ticket.
3. **Subject token**: the subject contains a valid ticket reference → attach to that ticket.
4. **No match**: create a new ticket, matching or creating the contact by sender address (FR-013).

The rule that matched is recorded on `InboundMessageLog.match_method`, so misthreading is
diagnosable rather than mysterious.

### Inbound behaviour rules
- An inbound message is always stored with `direction=INBOUND` and `visibility=PUBLIC`.
- An inbound message on a `RESOLVED` or `CLOSED` ticket reopens it to `OPEN` (spec edge case).
- A sender address unknown to the system creates a contact with **no organization** (FR-040), which
  then appears in the unlinked contacts list (FR-041).
- Arabic content survives decoding unchanged, including in the subject line (FR-035).
- An inbound message that cannot be processed is retained in `InboundMessageLog` with its error and
  is never dropped.

## Deployment dependencies

Both flows require, before end-to-end testing against a real mailbox:

1. A deliverable outbound address and a matching inbound route accepting `support+<token>@<domain>`.
2. Either a provider inbound webhook or IMAP credentials for polling.

Both are blocked on [ADR-006](../../../docs/decisions/006-deployment-target.md). Until they exist,
these contracts are tested against a local mail capture rather than a live mailbox.
