# Feature Specification: Live Chat

**Feature Branch**: `main` (no feature branch created; spec directory is `002-live-chat`)

**Created**: 2026-09-12

**Status**: Draft

**Input**: User description: "Live chat for the AZM CRM — the first feature after the MVP,
promoted ahead of WhatsApp and SMS by decision on 2026-09-11. A customer and an agent converse
in real time and the transcript persists onto a ticket; a supervisor can observe an in-progress
conversation with full customer context; that supervisor can send a private note to the agent
that the customer never sees."

## Scope

This specification covers live chat, the first channel after the MVP
([001-mvp-ticket-desk](../001-mvp-ticket-desk/spec.md)) and the first **synchronous** feature
in a product that is otherwise entirely asynchronous. That difference is the source of most of
what follows: a ticket can wait, a conversation cannot.

It is complete when this flow works:

> A visitor opens chat on the website and reaches an available agent within seconds. They
> converse in real time. A supervisor watches the conversation as it happens, sees who the
> customer is, and sends the agent a private note the customer never sees. When the
> conversation ends, the whole transcript is on a ticket and is part of that customer's
> permanent history.

**Requirement numbering**: requirements here are numbered independently of the MVP's.
References to the MVP's requirements are written as **MVP FR-0xx**.

**Explicitly out of scope**: WhatsApp, SMS, the knowledge base, the customer self-service
portal, AI-suggested replies, chatbots, automatic routing by skill or language, co-browsing,
voice or video, and file transfer during a chat. Each is sequenced separately.

**Reused rather than rebuilt**: the message visibility boundary (MVP FR-014, FR-015), ticket
references and lifecycle, contact matching, department and branch scoping (MVP FR-023,
FR-024), the audit trail (MVP FR-027), and bilingual Arabic/English with right-to-left layout
(MVP FR-031 to FR-036). Live chat introduces no second way to do any of these.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A visitor reaches an agent and they converse (Priority: P1)

A visitor on the public website opens the chat panel, gives their name and email, and is
connected to an available agent. Each sees the other's messages as they are sent, without
refreshing anything.

**Why this priority**: Without a conversation there is no feature. Everything else here
observes, records, or handles the absence of this.

**Independent Test**: With one agent online, open chat as a visitor, send a message, and see
the agent receive it and reply, both within seconds and without a page reload.

**Acceptance Scenarios**:

1. **Given** at least one agent is online with spare capacity, **When** a visitor submits the
   pre-chat form with a name and email, **Then** a conversation is created, assigned to that
   agent, and both parties see the conversation open.
2. **Given** an open conversation, **When** either party sends a message, **Then** the other
   sees it within two seconds without reloading the page.
3. **Given** an open conversation, **When** the agent is typing, **Then** the visitor is shown
   that a reply is being written.
4. **Given** a visitor whose email matches an existing contact, **When** the conversation
   starts, **Then** it is linked to that contact and their organization rather than creating a
   duplicate.
5. **Given** a visitor whose email is unknown, **When** the conversation starts, **Then** a
   contact is created with no organization, exactly as the request form does (MVP FR-040).
6. **Given** a visitor writing in Arabic, **When** they send a message, **Then** it is stored
   and displayed to the agent unchanged and right-to-left.
7. **Given** either party ends the conversation, **When** it closes, **Then** both are told it
   has ended and neither can add further messages to it.

---

### User Story 2 - An agent handles several conversations at once (Priority: P2)

An agent goes online, receives conversations up to their capacity, and moves between them from
one console without losing their place — with the customer's history beside each one.

**Why this priority**: One chat at a time is not a support desk. An agent's value in chat is
handling several while keeping each coherent, which is what makes capacity and presence
necessary rather than decorative.

**Independent Test**: With an agent set to a capacity of three, start three conversations and
confirm all three are reachable from the console, each showing unread counts and its own
history, and that a fourth is not assigned to them.

**Acceptance Scenarios**:

1. **Given** an agent signed in, **When** they set themselves online, **Then** they become
   eligible to receive conversations and colleagues can see they are available.
2. **Given** an agent at their capacity, **When** another visitor starts a chat, **Then** it is
   not assigned to that agent.
3. **Given** an agent with several open conversations, **When** a message arrives in one they
   are not currently viewing, **Then** they are shown which conversation it arrived in and how
   many messages are unread.
4. **Given** an agent viewing a conversation, **When** it loads, **Then** they see the
   customer's contact details, organization, and recent tickets alongside it.
5. **Given** an agent sets themselves offline, **When** they have open conversations, **Then**
   they are told those conversations must be ended or transferred first, rather than being
   abandoned silently.
6. **Given** an agent ends a conversation, **When** it closes, **Then** their capacity frees up
   and they become eligible for the next waiting visitor.

---

### User Story 3 - The conversation becomes a permanent record (Priority: P3)

When a conversation ends, its full transcript is on a ticket, findable by reference and on the
customer's timeline like anything else.

**Why this priority**: A conversation nobody can find afterwards is a phone call. This is what
makes chat part of the CRM rather than a widget bolted to the website.

**Independent Test**: Hold a conversation, end it, then find the ticket by reference and read
the whole exchange in order on the ticket thread.

**Acceptance Scenarios**:

1. **Given** a conversation starts, **When** it is created, **Then** a ticket is created with
   it, with a reference the customer can quote and an origin channel of chat.
2. **Given** a conversation ends, **When** the transcript is written, **Then** every message
   from both parties appears on the ticket thread in the order sent, each attributed and
   timestamped.
3. **Given** a completed chat ticket, **When** an agent opens the customer's organization,
   **Then** that ticket appears on the timeline exactly as an emailed one does.
4. **Given** a conversation the agent could not resolve, **When** it ends, **Then** the ticket
   remains open for follow-up rather than being closed automatically.
5. **Given** an agent realizes the conversation is about an existing ticket, **When** they
   attach it to that ticket, **Then** the transcript is written there, the placeholder ticket
   created at the start is soft-deleted, and both actions are audited.
6. **Given** a conversation ends, **When** the visitor is given a reference, **Then** it is the
   reference of the ticket the transcript actually landed on.
5. **Given** a conversation the agent resolved, **When** they end it and mark it resolved,
   **Then** the ticket is resolved, and a later customer reply reopens it as any other ticket
   would.
6. **Given** a transcript is written, **When** an administrator inspects the audit log,
   **Then** the conversation's creation, assignment and closure are recorded (MVP FR-027).

---

### User Story 4 - A supervisor watches a live conversation (Priority: P4)

A supervisor opens a conversation that is happening now and reads it as it unfolds, with the
customer's context beside it, without the customer knowing and without interrupting the agent.

**Why this priority**: Live chat is where a new agent is most exposed and where a mistake
reaches the customer instantly, with no draft to review. Observation is how a supervisor coaches
and catches trouble before it lands.

**Who this is**: the Supervisor role added by FR-037 — a team lead who can watch and coach
within their own department, and who deliberately cannot create accounts or read the audit log.

**Independent Test**: With a conversation in progress, open it as a supervisor and see new
messages appear as they are sent, without appearing in the conversation as a participant.

**Acceptance Scenarios**:

1. **Given** a conversation in progress, **When** a supervisor opens it, **Then** they see the
   messages so far and each new one as it is sent.
2. **Given** a supervisor is observing, **When** the customer looks at the conversation,
   **Then** there is no indication anyone else is present.
3. **Given** a supervisor is observing, **When** they attempt to send a message to the
   customer, **Then** they cannot: observation does not make them a participant.
4. **Given** a supervisor opens a conversation, **When** it loads, **Then** they see the
   customer's contact, organization and recent tickets, as the agent does.
5. **Given** a supervisor observes a conversation, **When** they do, **Then** the observation
   itself is recorded — who watched whose conversation, and when.
6. **Given** a conversation outside the supervisor's department or branch, **When** they try to
   open it, **Then** it is not disclosed to them (MVP FR-024).

---

### User Story 5 - A supervisor coaches the agent privately (Priority: P5)

While the conversation is live, the supervisor sends the agent a note only the agent sees —
correcting a price, warning about a commitment, suggesting wording.

**Why this priority**: This is the reason the message visibility boundary was built into the
MVP ahead of time. It is also the single most damaging thing in the product if it leaks: a
private staff remark delivered into a customer's chat window, in real time, unrecallable.

**Independent Test**: Send a whisper during a live conversation. Confirm the agent sees it,
the customer's view does not change in any way, and the transcript given to the customer never
contains it.

**Acceptance Scenarios**:

1. **Given** a supervisor observing a live conversation, **When** they send a private note,
   **Then** the agent sees it within two seconds, marked clearly as private and not part of the
   conversation.
2. **Given** a private note has been sent, **When** the customer's view updates, **Then**
   nothing about it changes — no message, no notification, no indication of activity.
3. **Given** a conversation containing private notes, **When** the transcript is written to the
   ticket, **Then** the notes are stored as internal messages, visible to staff and to no
   customer-facing output (MVP FR-015).
4. **Given** a conversation containing private notes, **When** a transcript is sent or shown to
   the customer, **Then** it contains the conversation only.
5. **Given** an agent viewing their conversation, **When** a private note arrives, **Then** it
   is unmistakably distinct from the customer's messages by more than colour alone.
6. **Given** an agent replies to the customer immediately after a private note, **When** they
   send, **Then** the note's content is not included and the two cannot be confused in the
   sending interface.

---

### User Story 6 - Everyone is busy, or the desk is closed (Priority: P6)

A visitor arrives when every agent is at capacity, and waits with a position that moves. A
visitor who arrives when nobody is online is not offered chat at all — they see the request
form, because a queue behind nobody is a waiting room with no door.

**Why this priority**: This is the most common experience of a chat feature, and the one most
often left to a spinner that never resolves. Handled badly it converts a customer with a
question into a customer with a complaint.

**Independent Test**: With no agents online, confirm chat is not offered and the request form
is. Then bring an agent online at capacity and confirm a visitor queues with a position that
updates.

**Acceptance Scenarios**:

1. **Given** all online agents are at capacity, **When** a visitor starts a chat, **Then** they
   are placed in a queue and shown their position, which updates as it changes.
2. **Given** a visitor is waiting, **When** an agent becomes free, **Then** the longest-waiting
   visitor is connected first.
3. **Given** no agent is online at all, **When** a visitor opens the website, **Then** chat is
   not offered and the request form is presented in its place.
4. **Given** a visitor is waiting in the queue, **When** the last online agent goes offline,
   **Then** the visitor is offered the request form immediately, with anything they already
   typed carried into it, rather than being left queued for a desk that has closed.
5. **Given** a visitor leaves the queue, **When** they close the panel, **Then** they are
   removed from it and no agent is assigned a conversation nobody is waiting on.

---

### User Story 7 - A connection drops (Priority: P7)

A network hiccup, a closed laptop, or a phone going into a tunnel does not lose the
conversation or strand the other party.

**Why this priority**: Every real chat session is on a network that fails sometimes. Without
this the failure mode is an agent talking to nobody and a customer who thinks they were
ignored.

**Independent Test**: Interrupt the visitor's connection mid-conversation and restore it.
Confirm the conversation resumes with its history intact and nothing sent in between was lost.

**Acceptance Scenarios**:

1. **Given** a visitor's connection drops briefly, **When** it returns within the grace period,
   **Then** the same conversation resumes with its full history.
2. **Given** a visitor's connection drops, **When** the grace period passes, **Then** the
   conversation ends, the transcript is saved, and the agent is told the customer disconnected
   rather than being left waiting.
3. **Given** an agent's connection drops, **When** the grace period passes, **Then** the
   conversation returns to the queue for another agent, with its history, and the customer is
   told they are being reconnected.
4. **Given** a message was sent while the other party was briefly disconnected, **When** they
   reconnect, **Then** they receive it.
5. **Given** a conversation has been idle beyond the inactivity limit, **When** the limit
   passes, **Then** both parties are warned before it closes, not after.

---

### Edge Cases

- Two supervisors observe the same conversation at once. Both see it; neither is visible to the
  customer; both observations are recorded.
- A supervisor whispers to an agent who has just disconnected. The note waits for them rather
  than vanishing, and is not delivered to whoever takes the conversation over.
- The customer sends a message at the exact moment the agent ends the conversation. The message
  is not lost — it either lands in the conversation or reopens it, never silently discarded.
- A visitor opens chat in two browser tabs. They are one conversation, not two, and an agent is
  not assigned twice.
- A visitor pastes a very long message, or content in a script other than Arabic or Latin. It is
  stored intact or rejected with a stated limit, never truncated silently.
- An agent is deactivated mid-conversation (MVP FR-026). Their access ends immediately and the
  conversation returns to the queue rather than being stranded on a disabled account.
- The customer's browser is left open overnight on an ended conversation. Reopening it does not
  resurrect the conversation or leak a later one into the same window.
- Chat is opened by someone who is already a contact of two organizations. The conversation is
  linked to the contact, and the organization is the one their contact record currently names.
- The last online agent goes offline while someone is queued. The waiting visitor is moved to
  the request form immediately rather than left waiting for a desk that has closed.
- An agent attaches a conversation to a ticket in another department. It is refused: a ticket
  they cannot see is a ticket they cannot attach to (MVP FR-024).
- A Supervisor is themselves handling a conversation and observes another at the same time.
  Both are permitted; their own capacity is unaffected by observing.
- A whisper is sent a moment before the conversation ends. It reaches the transcript as an
  internal message, or not at all — never as a customer-visible one.

## Requirements *(mandatory)*

### Functional Requirements

**Starting a conversation**

- **FR-001**: System MUST offer a chat entry point on the public website that states whether
  anyone is available before the visitor commits to waiting.
- **FR-002**: System MUST collect a name and email address before a conversation starts, and
  MUST match or create a contact from them exactly as the request form does (MVP FR-002,
  FR-040).
- **FR-003**: System MUST create a ticket for every conversation, with a quotable reference and
  an origin channel of chat.
- **FR-004**: System MUST assign a new conversation to an online agent with spare capacity
  within the visitor's department and branch scope.
- **FR-005**: System MUST NOT require the visitor to have an account, since customer
  self-service arrives in a later phase.

**Conversing**

- **FR-006**: System MUST deliver a message to the other party within two seconds without
  either page being reloaded.
- **FR-007**: System MUST show each party when the other is composing a message.
- **FR-008**: System MUST record every message with an author, a timestamp, and a visibility of
  public or internal, reusing the MVP's message model rather than introducing a second one.
- **FR-009**: System MUST allow either party to end a conversation, and MUST tell the other
  when it has ended.
- **FR-010**: System MUST store and display Arabic content unchanged and right-to-left, in the
  visitor panel as well as the agent console (MVP FR-031 to FR-035).

**Agent presence and capacity**

- **FR-011**: Agents MUST be able to set themselves online or offline, and MUST NOT receive
  conversations while offline.
- **FR-012**: System MUST enforce a maximum number of simultaneous conversations per agent and
  MUST NOT exceed it when assigning.
- **FR-013**: System MUST show an agent, across all their conversations, which have unread
  messages and how many.
- **FR-014**: System MUST prevent an agent from going offline while holding open conversations
  without first ending or transferring them.
- **FR-015**: System MUST show the agent the customer's contact, organization and recent
  tickets alongside the conversation.

**Waiting**

- **FR-016**: System MUST queue a visitor when no agent has capacity, and MUST show their
  position and update it as it changes.
- **FR-017**: System MUST connect the longest-waiting visitor first.
- **FR-018**: System MUST offer the request form instead of a queue when no agent is online at
  all, and MUST carry anything already typed into it.
- **FR-019**: System MUST remove a visitor from the queue when they leave, so no agent is
  assigned a conversation nobody is waiting on.

**Supervision**

- **FR-020**: Supervisors MUST be able to observe a live conversation within their department
  and branch scope, seeing new messages as they are sent.
- **FR-021**: System MUST NOT disclose to the customer that a conversation is being observed.
- **FR-022**: System MUST prevent an observer from sending a message to the customer.
- **FR-023**: System MUST record each observation — who observed which conversation, and when.
- **FR-024**: Supervisors MUST be able to send a private note to the agent during a live
  conversation, delivered within two seconds.
- **FR-025**: System MUST store private notes as internal messages and MUST exclude them from
  every customer-facing output, including any transcript (MVP FR-015).
- **FR-026**: System MUST make a private note unmistakably distinct from customer messages in
  the agent's view, by more than colour alone.
- **FR-027**: System MUST make it impossible to send a private note to the customer by mistake:
  the two destinations MUST be separate controls, not one control with a mode.

**The record**

- **FR-028**: System MUST write the full transcript to the conversation's ticket when it ends,
  preserving order, attribution and timestamps.
- **FR-029**: System MUST leave an unresolved conversation's ticket open, and MUST allow the
  agent to resolve it at the point of ending the conversation.
- **FR-030**: System MUST show chat tickets on the customer timeline identically to tickets
  from any other channel (MVP FR-019).
- **FR-031**: System MUST record conversation creation, assignment, observation and closure in
  the audit trail (MVP FR-027).

**Interruption**

- **FR-032**: System MUST resume a conversation with its full history when a party reconnects
  within the grace period.
- **FR-033**: System MUST end a conversation and save its transcript when a visitor does not
  return within the grace period, and MUST tell the agent why.
- **FR-034**: System MUST return a conversation to the queue, with its history, when an agent
  does not return within the grace period.
- **FR-035**: System MUST deliver messages sent while a party was briefly disconnected once
  they reconnect.
- **FR-036**: System MUST warn both parties before closing an idle conversation, not after.

**Roles, ticket linking and availability** *(decided 2026-09-12)*

- **FR-037**: System MUST support a third role, **Supervisor**, in addition to Agent and
  Administrator. A Supervisor can do everything an Agent can, and additionally observe live
  conversations and send private notes within their own department and branch. A Supervisor
  MUST NOT be able to create or deactivate accounts, change anyone's department or branch, or
  read the audit log — those remain Administrator-only.

  *This amends MVP FR-022, which fixed the role set at two. The role set stays fixed in code
  and stays non-configurable by users; it is the count that changes, deliberately, because
  coaching an agent and administering the system are different jobs and giving one person both
  to get the first was the wrong trade.*

- **FR-038**: Agents MUST be able to attach a conversation to an existing ticket during the
  conversation, once they understand what it is about. The visitor is never asked for a ticket
  reference and is never shown one they did not already have: an email address typed into a
  pre-chat form is not proof of identity, so a visitor MUST NOT be able to reach an existing
  ticket by naming it.

- **FR-039**: System MUST NOT offer chat at all when no agent is online, showing the request
  form instead. Queuing applies only when agents are online and all are at capacity — a queue
  behind nobody is a waiting room with no door.

**Consequences of those decisions**

- **FR-040**: System MUST create the conversation's ticket when the conversation starts, so a
  transcript can never be orphaned by an unexpected ending, but MUST NOT give the visitor a
  ticket reference until the conversation ends — by then the agent may have attached it to an
  existing ticket, and a reference handed out early could be one the customer can no longer
  use.
- **FR-041**: When an agent attaches a conversation to an existing ticket, the system MUST
  write the transcript to that ticket, MUST soft-delete the placeholder ticket created at the
  start, and MUST record both actions in the audit trail (MVP FR-020, FR-027).
- **FR-042**: System MUST offer the request form immediately to anyone already waiting when
  the last online agent goes offline, rather than leaving them queued for a desk that has
  closed.
- **FR-043**: System MUST scope a Supervisor's observation to their own department and branch,
  with an out-of-scope conversation undisclosed exactly as any other record (MVP FR-024).

### Key Entities

- **Conversation**: One live chat session. Belongs to a ticket, a contact, a department and a
  branch. Has a state (waiting, active, ended), an assigned agent, and timestamps for start,
  assignment and end.
- **Chat message**: One entry in a conversation, reusing the MVP's message model — an author,
  a direction, a **visibility of public or internal**, and a timestamp. A private note is an
  internal one.
- **Agent presence**: Whether an agent is online and how many conversations they currently
  hold, against their maximum.
- **Queue entry**: A waiting visitor with the time they arrived, used to connect the
  longest-waiting first and to show a position.
- **Observation**: A record that a named Supervisor watched a named conversation, with the time
  — auditable in its own right, because watching a colleague's conversation is an exercise of
  authority, not a neutral read.
- **Supervisor**: A third role alongside Agent and Administrator (FR-037). Works tickets like
  an Agent, and additionally observes and coaches within their own department and branch.
  Cannot administer accounts or read the audit log.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A visitor reaches an available agent in under 30 seconds when one has capacity.
- **SC-002**: A message appears for the other party in under 2 seconds on a normal connection.
- **SC-003**: 100% of conversations produce a findable ticket carrying the complete transcript;
  none are lost, including those ended by a disconnection.
- **SC-004**: 0 private notes appear in any customer-facing output, verified by automated test
  on every build.
- **SC-005**: 0 customers are shown any indication that their conversation is being observed,
  verified by automated test on every build.
- **SC-006**: An agent handles three simultaneous conversations without losing their place or
  missing a message, verified with agents before release.
- **SC-007**: 100% of visitors who cannot be served are given a working alternative rather than
  an unresolved wait.
- **SC-008**: A conversation survives a 30-second network interruption with no message lost.
- **SC-009**: The chat panel and agent console are fully usable in Arabic with right-to-left
  layout, verified by review before release.
- **SC-010**: Supervisors can identify a coachable moment and reach the agent privately before
  the agent's next message is sent, in the judgement of the supervisors themselves after two
  weeks of use.

## Assumptions

- The MVP ([001-mvp-ticket-desk](../001-mvp-ticket-desk/spec.md)) is deployed and its email
  channel is working. Chat is an additional channel, not a replacement.
- Visitors are anonymous: there is no customer login until the portal phase, so identity comes
  from the pre-chat form and is no stronger than an email address typed by the visitor.
- Agent capacity defaults to three simultaneous conversations, adjustable per agent by an
  administrator.
- The reconnection grace period is assumed to be 60 seconds, and the idle limit 10 minutes with
  a warning at 8. Confirm both with agents before release; they are the numbers most likely to
  feel wrong in practice.
- There is no maximum queue wait, because chat is only offered while agents are online (FR-039)
  and a queue that exists only while the desk is staffed is bounded by the desk itself. If
  waits turn out to be long in practice, a cap is a small addition.
- A conversation is always attached to exactly one ticket, created when the conversation
  starts, so a transcript can never be orphaned by an unexpected ending.
- Chat is offered on the public website only, not inside a customer portal that does not exist,
  and only while at least one agent is online (FR-039).
- A visitor's identity is no stronger than an email address they typed, which is why they can
  never reach an existing ticket by naming it (FR-038). Attaching a conversation to an existing
  ticket is a staff action, taken by someone who can already see both.
- Adding the Supervisor role means an existing account must be moved to it deliberately; no
  account becomes a Supervisor by upgrade, and Agent remains the default.
- Conversations are scoped by department and branch like every other record; the department is
  determined the same way the request form determines it.
- No file transfer during a conversation in this phase, even though tickets support
  attachments. A file arriving mid-conversation is a separate capability with its own
  scanning and size questions.
- Transcripts are retained for the same period as the tickets they belong to.
