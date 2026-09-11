# Feature Specification: MVP Ticket Desk

**Feature Branch**: `main` (no feature branch created; spec directory is `001-mvp-ticket-desk`)

**Created**: 2026-09-11

**Status**: Draft

**Input**: User description: "Scope for THIS spec: MVP (Phase 1) only. Build a specification for the MVP of the AZM CRM. For each capability, produce user stories with acceptance criteria, following the SpecKit spec template. Reference: docs/requirements/azm_squad_customer_support_crm.pdf, docs/roadmap.md"

## Scope

This specification covers the Phase One MVP defined in [`docs/roadmap.md`](../../docs/roadmap.md)
(work items M1–M9). The MVP is a vertical slice, not a complete CRM. It is complete when this
single flow works in production:

> A customer submits a request through a web form. A ticket is created and linked to a customer
> record. An agent sees it in their queue, takes it, replies by email, and resolves it. Every step
> is recorded in the audit log, and the customer's full history is reconstructable.

**Explicitly out of scope for this specification**: SLA targets and automation, live chat,
WhatsApp, SMS, knowledge base, customer self-service portal, reports and dashboards, AI features,
ERP and external integrations, tasks and reminders, quick replies, custom branding, and
agent-configurable roles. Each is sequenced in the roadmap and specified separately.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Capture an incoming request as a ticket (Priority: P1)

A person with a support need fills in a public web form with their name, contact details, a
subject, and a description of their problem. The system records them as a customer (or recognizes
them if they have contacted before), creates a ticket linked to that customer, gives the ticket a
reference the customer can quote, and confirms receipt by email.

**Why this priority**: Without intake there is no work in the system. Every other story operates
on tickets this story creates. It is also the only story that involves someone outside the
organization, so it is where data loss is least recoverable.

**Independent Test**: Submit the public web form with valid details and confirm a ticket appears in
the unassigned queue, linked to a customer record, with a confirmation email sent to the submitter.
Delivers value on its own: requests stop being lost in personal inboxes.

**Acceptance Scenarios**:

1. **Given** a visitor on the public request form, **When** they submit valid name, email, subject,
   and description, **Then** the system creates a ticket in status "New", links it to a customer
   record, displays a ticket reference, and sends a confirmation email containing that reference.
2. **Given** a visitor whose email address already belongs to a known contact, **When** they submit
   the form, **Then** the system links the new ticket to that contact and to the contact's customer
   organization, rather than creating a duplicate contact.
3. **Given** a visitor whose email address is unknown, **When** they submit the form, **Then** the
   system creates a contact with no organization, links the ticket to it, and presents that contact
   to staff as needing to be linked to an organization.
3. **Given** a visitor who omits a required field, **When** they submit, **Then** the system rejects
   the submission, states which fields are required, and preserves the text they already typed.
4. **Given** a visitor using the form in Arabic, **When** they submit Arabic text in the subject and
   description, **Then** that text is stored and later displayed to the agent without corruption.
5. **Given** a submission is accepted, **When** an administrator inspects the audit log, **Then** an
   entry records the ticket creation with timestamp and the originating channel.

---

### User Story 2 - Agent resolves a ticket end to end (Priority: P2)

An agent signs in, sees the tickets available to them, opens one, reads the customer's request and
history, replies to the customer by email from within the ticket, and moves the ticket through to
resolved. The reply and the status change are both recorded on the ticket.

**Why this priority**: This is the core working loop and the reason the product exists. It depends
on Story 1 for input but delivers the actual support outcome.

**Independent Test**: With a ticket already in the queue, sign in as an agent, open it, send a
reply, and resolve it. Confirm the customer receives the reply by email and the ticket history
shows both events with actor and timestamp.

**Acceptance Scenarios**:

1. **Given** an agent signed in, **When** they open their queue, **Then** they see every ticket in
   their department and branch with reference, subject, organization, contact, priority, status,
   assigned agent, and age, most urgent first, and can narrow it to the tickets assigned to them.
2. **Given** an unassigned ticket in the queue, **When** the agent takes it, **Then** the ticket is
   assigned to that agent and is no longer available for another agent to take.
3. **Given** a ticket assigned to one agent, **When** an administrator reassigns it to another,
   **Then** the new assignment takes effect and the reassignment is recorded with both agents named.
3. **Given** an agent viewing an assigned ticket, **When** they compose and send a reply, **Then**
   the reply is delivered to the customer by email and appears on the ticket thread attributed to
   that agent with a timestamp.
4. **Given** a customer replies to that email, **When** the reply is received, **Then** it is
   appended to the same ticket thread rather than creating a new ticket.
5. **Given** an agent viewing a ticket, **When** they change its category, priority, or status,
   **Then** the change takes effect immediately and is recorded in the ticket history with the
   previous and new values.
6. **Given** an agent resolves a ticket, **When** they confirm, **Then** the ticket status becomes
   "Resolved", it leaves the active queue, and it remains findable by reference and by customer.

---

### User Story 3 - Maintain customer organizations, contacts, and history (Priority: P3)

An agent or administrator opens a customer organization to see who it is, which people work there,
every ticket raised by any of them, and the notes colleagues have left. They can correct contact
details, add notes, and link a newly arrived contact to the right organization.

**Why this priority**: Context is what separates a CRM from a shared mailbox. It is needed for good
service but a ticket can technically be answered without it.

**Independent Test**: Create a customer, add contact details and a note, raise two tickets for them,
then confirm the customer record shows both tickets and the note on a single timeline.

**Acceptance Scenarios**:

1. **Given** an agent viewing a customer organization, **When** the record loads, **Then** it shows
   the organization's identifying details, its contacts, and a timeline combining the tickets raised
   by all of those contacts with the notes held against it, in reverse chronological order.
2. **Given** a contact that belongs to no organization, **When** an agent links it to an
   organization, **Then** that contact's existing tickets appear on the organization's timeline and
   the link is audited.
2. **Given** an agent editing a customer's contact details, **When** they save a valid change,
   **Then** the new value is stored and the previous value remains recoverable from the audit log.
3. **Given** an agent on a customer record, **When** they add a note, **Then** the note appears on
   the timeline attributed to them with a timestamp.
4. **Given** an administrator deletes a customer, **When** they confirm, **Then** the record is
   hidden from normal listings but retained and recoverable, and the deletion is audited.
5. **Given** a customer has no tickets yet, **When** an agent views the record, **Then** the
   timeline states that clearly rather than appearing broken or empty without explanation.

---

### User Story 4 - Administrator controls who can see and do what (Priority: P4)

An administrator creates accounts for agents, assigns each to a department and branch, and relies
on the system to refuse any action the account is not permitted to perform. Agents cannot reach
data outside their permitted scope, whether through the interface or by guessing a direct address.

**Why this priority**: The constitution requires deny-by-default authorization on every action.
Building it after the working loop would mean auditing every screen already shipped.

**Independent Test**: Create an agent account limited to one department, then attempt to open a
ticket belonging to another department directly by its reference. The attempt must be refused.

**Acceptance Scenarios**:

1. **Given** a signed-out visitor, **When** they request any page other than the public request form
   or the sign-in page, **Then** access is refused and they are directed to sign in.
2. **Given** a signed-in agent, **When** they attempt an administrator-only action, **Then** the
   action is refused with a clear message and the attempt is recorded.
3. **Given** an agent belonging to one department, **When** they request a ticket belonging to
   another department by its direct address, **Then** access is refused and the ticket's existence
   is not disclosed.
4. **Given** an administrator creating a user, **When** they save, **Then** the new account has
   exactly one role and at least one department, and cannot sign in until a password is set.
5. **Given** a user account is deactivated, **When** that user attempts to sign in or continue an
   existing session, **Then** access is refused immediately.

---

### User Story 5 - Every change is auditable (Priority: P5)

An administrator investigating a dispute can determine who changed a customer or ticket record,
when, and what the values were before and after.

**Why this priority**: Required by constitution Principle II. It is invisible during normal use and
indispensable the first time a customer disputes what was said or promised.

**Independent Test**: Change a ticket's priority, then query the audit log for that ticket and
confirm the entry names the actor, the time, the field, and both values.

**Acceptance Scenarios**:

1. **Given** any change to a customer, contact, note, ticket, or user record, **When** the change is
   saved, **Then** an audit entry records actor, timestamp in UTC, entity, action, and the before and
   after values of each changed field.
2. **Given** an administrator viewing the audit log, **When** they filter by entity, actor, or date
   range, **Then** only matching entries are returned.
3. **Given** any user including an administrator, **When** they attempt to edit or delete an audit
   entry, **Then** the attempt is refused.
4. **Given** a record is soft-deleted, **When** an administrator reviews the audit log, **Then** the
   deletion is present as an auditable action with its actor.
5. **Given** an audit entry concerns a field holding sensitive personal data, **When** it is stored,
   **Then** it does not expose credentials or secret material in readable form.

---

### User Story 6 - Work in Arabic or English (Priority: P6)

An Arabic-speaking agent uses the system entirely in Arabic with a right-to-left layout. An
English-speaking colleague uses the same system in English, left to right. Either can switch.

**Why this priority**: Decided as a launch requirement on 2026-09-11. It is a gate on every screen
rather than a screen of its own, which is why it is stated once here as a story and enforced on all
the others.

**Independent Test**: Switch the interface to Arabic and complete the full flow from Story 2. Every
label, message, date, and control must render in Arabic with correct right-to-left layout.

**Acceptance Scenarios**:

1. **Given** a user with Arabic selected, **When** they open any screen in this specification,
   **Then** all interface text is in Arabic and the layout reads right to left.
2. **Given** a user switches language, **When** the page reloads, **Then** the choice persists across
   their session and subsequent sign-ins.
3. **Given** a ticket containing Arabic text, **When** it is displayed in the English interface,
   **Then** the customer's Arabic content is still rendered correctly.
4. **Given** any date, time, or number shown to a user, **When** it is displayed, **Then** it is
   formatted according to the selected language.
5. **Given** an email sent to a customer, **When** it is composed, **Then** it uses the language the
   customer used when contacting, defaulting to Arabic when unknown.

---

### User Story 7 - Internal messages never reach the customer (Priority: P7)

A colleague adds a message to a ticket that is meant for the team only. The customer never sees it,
in any view, any email, or any export.

**Why this priority**: The MVP does not yet include the supervisor whisper feature this protects,
but the roadmap places live chat immediately after launch. Establishing the visibility boundary now
costs one field and one test, and prevents a privacy failure later.

**Independent Test**: Add an internal message to a ticket, then inspect every customer-facing output
for that ticket and confirm the message is absent from all of them.

**Acceptance Scenarios**:

1. **Given** an agent composing a message on a ticket, **When** they mark it internal, **Then** it is
   stored as internal and shown to permitted staff only.
2. **Given** a ticket with both public and internal messages, **When** any customer-facing output is
   produced, **Then** it contains the public messages only.
3. **Given** an internal message exists, **When** an email is sent to the customer, **Then** the
   internal message is not included in the message body or any quoted history.
4. **Given** an agent views a ticket, **When** the thread is displayed, **Then** internal and public
   messages are visually distinct and unambiguous.

---

### Edge Cases

- Two people submit the form with the same email address but different names. The system links both
  tickets to one contact and does not silently overwrite the stored name.
- A contact is linked to the wrong organization and later moved. Tickets keep the organization they
  were raised under, so historical records stay truthful.
- Several unlinked contacts share an email domain. Staff can see them together when deciding whether
  they belong to one organization, but the system does not link them automatically.
- A customer replies to a ticket that has already been resolved. The reply is appended and the
  ticket returns to an active status rather than being lost.
- Outbound email delivery fails. The failure is visible to the agent on the ticket rather than
  silently discarded, and the reply remains on the thread.
- Two agents attempt to take the same unassigned ticket at the same moment. Exactly one succeeds and
  the other is told the ticket is already assigned.
- A form submission contains an extremely long description, or content in a script other than Arabic
  or Latin. It is stored intact or rejected with a stated limit, never truncated silently.
- An agent's session expires while they are composing a reply. They are not signed out into a lost
  draft without warning.
- A customer's email address changes. Historical tickets remain attached to the customer record.
- An inbound email arrives that matches no existing ticket reference. It creates a new ticket rather
  than being discarded.
- The public form receives automated spam submissions. The system limits abuse without blocking
  legitimate customers.

## Requirements *(mandatory)*

### Functional Requirements

**Intake**

- **FR-001**: System MUST provide a publicly reachable request form capturing submitter name, email
  address, subject, and description, with optional phone number.
- **FR-002**: System MUST create a ticket for every accepted submission and link it to a contact,
  matching an existing contact by email address when one exists and using that contact's
  organization.
- **FR-003**: System MUST assign every ticket a human-quotable reference that is unique and stable.
- **FR-004**: System MUST send the submitter a confirmation containing the ticket reference.
- **FR-005**: System MUST reject incomplete or invalid submissions with field-level messages and
  MUST preserve already-entered content.
- **FR-006**: System MUST limit abusive or automated submission volume from the public form.

**Tickets**

- **FR-007**: System MUST record for each ticket: reference, customer organization, requesting
  contact, subject, description, category, priority, status, assigned agent, department, branch,
  origin channel, and timestamps.
- **FR-008**: System MUST prevent a ticket already assigned to one agent from being taken by
  another without an explicit reassignment action, and MUST record who performed it.
- **FR-009**: System MUST enforce a defined status lifecycle and MUST reject transitions outside it.
- **FR-010**: System MUST record every ticket field change, message, assignment, and status
  transition on a ticket history visible to permitted staff.
- **FR-011**: Users MUST be able to search and filter tickets by reference, customer, status,
  priority, category, and assigned agent.

**Messaging**

- **FR-012**: Users MUST be able to send a reply to the customer from within a ticket, delivered by
  email, and recorded on the ticket thread attributed to the sender.
- **FR-013**: System MUST attach inbound customer email replies to the originating ticket, and MUST
  create a new ticket when no originating ticket can be determined.
- **FR-014**: System MUST record every message with a visibility of either public or internal.
- **FR-015**: System MUST exclude internal messages from every customer-facing output, including
  interface views, emails, and exports.
- **FR-016**: System MUST surface outbound delivery failures to staff on the affected ticket.

**Customers**

- **FR-017**: System MUST maintain customer organization records, and contact records holding the
  contact's name and means of reaching them.
- **FR-018**: Users MUST be able to add notes to a customer record, attributed and timestamped.
- **FR-019**: System MUST present a single organization timeline combining the tickets raised by
  every one of its contacts together with the notes held against it, and MUST also allow that
  timeline to be narrowed to one contact.
- **FR-020**: System MUST soft-delete customer-facing records by default and MUST retain them as
  recoverable.

**Access control**

- **FR-021**: System MUST refuse every request that is not explicitly authorized for the acting
  account, with no permissive default.
- **FR-022**: System MUST support the roles Agent and Administrator in the MVP, with permissions
  fixed in code rather than configurable by users.
- **FR-023**: System MUST scope every data query by the acting user's department and branch.
- **FR-024**: System MUST NOT disclose the existence of records outside the acting user's scope.
- **FR-025**: Administrators MUST be able to create, deactivate, and reassign the department and
  branch of user accounts.
- **FR-026**: System MUST terminate access immediately when an account is deactivated.

**Audit**

- **FR-027**: System MUST write an audit entry for every create, update, and delete of a customer,
  contact, note, ticket, message, or user record, capturing actor, UTC timestamp, entity, action,
  and changed-field before and after values.
- **FR-028**: System MUST make audit entries immutable to all roles.
- **FR-029**: Administrators MUST be able to filter the audit log by entity, actor, and date range.
- **FR-030**: System MUST exclude credentials and secret material from audit entries, logs, and
  error output.

**Language and presentation**

- **FR-031**: System MUST present every screen in this specification in both Arabic and English.
- **FR-032**: System MUST render right-to-left layout correctly when Arabic is selected.
- **FR-033**: System MUST persist each user's language choice across sessions.
- **FR-034**: System MUST format dates, times, and numbers according to the selected language.
- **FR-035**: System MUST store and display Arabic content without corruption at every boundary,
  including email.
- **FR-036**: System MUST be usable on current mobile browser screen sizes as well as desktop.

**Customer structure and work distribution** *(decided 2026-09-11)*

- **FR-037**: System MUST model a customer as an organization that holds one or more named contacts.
  Every ticket MUST record both the customer organization and the individual contact who raised it.
- **FR-038**: Agents MUST be able to see every ticket within their own department and branch,
  regardless of who it is assigned to.
- **FR-039**: Agents MUST be able to take an unassigned ticket from the shared queue themselves, and
  administrators MUST be able to assign or reassign any ticket within their scope to any agent.
  Automatic assignment is out of MVP scope.
- **FR-040**: System MUST create a contact for every accepted form submission, and MUST leave that
  contact's organization unset when it cannot be determined rather than guessing one.
- **FR-041**: System MUST make contacts without an organization visible to staff as needing
  attention, and MUST allow staff to link such a contact to an existing or new organization.
- **FR-042**: Users MUST be able to move a contact from one organization to another, and every ticket
  MUST retain the organization it was raised under at the time it was created.

### Key Entities

- **User**: A staff member who signs in. Has a role, a department, a branch, a language preference,
  and an active or deactivated state.
- **Role**: Agent or Administrator in the MVP. Determines permitted actions.
- **Department**: An organizational unit that scopes data visibility.
- **Branch**: A location that scopes data visibility. Single branch at launch; the concept exists so
  later multi-branch operation needs no data migration.
- **Customer**: An organization that receives support. Holds identifying details, one or more
  contacts, notes, and the combined ticket history of all its contacts.
- **Contact**: A named person belonging to a customer organization, holding their own means of
  contact. A contact may temporarily belong to no organization, pending staff review.
- **Contact detail**: A means of reaching a contact, such as an email address or phone number.
- **Note**: Free text recorded against a customer by a staff member, attributed and timestamped.
- **Ticket**: A single request for support, belonging to a customer, with category, priority,
  status, assignment, department, branch, origin channel, and a reference.
- **Message**: One entry on a ticket thread, with an author, a direction (inbound or outbound), a
  visibility (public or internal), a channel, and a delivery outcome.
- **Audit entry**: An immutable record of one change, naming actor, time, entity, action, and the
  before and after values of changed fields.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A customer can submit a request and receive a confirmation with a usable reference in
  under two minutes without assistance.
- **SC-002**: An agent can go from opening their queue to sending a first reply in under 60 seconds
  for a ticket needing no research.
- **SC-003**: 100% of requests submitted through the form become tickets; none are lost, and none
  create a duplicate contact for an email address already on file.
- **SC-004**: 100% of changes to customer and ticket records are reconstructable from the audit log,
  verified by sampling.
- **SC-005**: 0 internal messages appear in any customer-facing output, verified by automated test
  on every build.
- **SC-006**: 0 successful accesses to records outside the acting user's department and branch scope,
  verified by automated test on every build.
- **SC-007**: Every screen in scope is fully usable in both Arabic and English, with no untranslated
  text and no left-to-right layout defects in Arabic, verified by review before release.
- **SC-008**: Agents complete the full flow from queue to resolution on first attempt without
  training beyond a one-page guide, verified with at least three agents before release.
- **SC-009**: Ticket listings and customer timelines remain responsive with at least 50,000 tickets
  and 10,000 customers on file.
- **SC-010**: The system supports the organization's full agent population working concurrently
  without noticeable slowdown.

## Assumptions

- The requirements source is `docs/requirements/azm_squad_customer_support_crm.pdf`. The path given
  in the command (`docs/requirements/project-requirements.pdf`) does not exist in the repository.
- Phase 0 foundation work (project skeleton, continuous integration, quality gates, migrations, and
  architecture decisions 1 through 5 in the roadmap) is a prerequisite of this specification and is
  not itself specified here, having no user-facing behavior.
- The ticket status lifecycle is assumed to be New, Open, Pending Customer, Resolved, Closed, with
  reopening permitted from Resolved. Confirm with stakeholders before implementation.
- Ticket priorities are assumed to be Low, Normal, High, Urgent, with Normal as the default.
- Ticket categories are assumed to be administrator-maintained values rather than fixed in code.
- The public request form does not require the submitter to have an account. Self-service login for
  customers arrives with the customer portal in a later phase.
- Customers receive updates by email only in the MVP.
- Authentication is assumed to be email and password with session management, supplied by the chosen
  framework rather than built from scratch.
- File attachments on customer notes and tickets are in scope but are the first item to drop if the
  MVP schedule is at risk, per the roadmap.
- The organization operates a single branch at launch, while the data model supports several.
- No existing customer or ticket data is migrated into the MVP. Confirm before implementation.
- A customer is an organization with named contacts, decided 2026-09-11. Consumer-style support for
  individuals with no employer is handled by an organization holding a single contact.
- Agents see all tickets in their own department and branch, decided 2026-09-11.
- Agents pull tickets from a shared queue and administrators may reassign, decided 2026-09-11.
- Data retention follows industry-standard practice for customer support records until a specific
  legal obligation is identified.
