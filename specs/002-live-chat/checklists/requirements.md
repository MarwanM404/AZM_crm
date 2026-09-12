# Specification Quality Checklist: Live Chat

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-12
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

All items pass. Ready for `/speckit-plan`.

**Three clarifications raised and resolved on 2026-09-12:**

- **FR-037 — who may observe and whisper**: a third role, Supervisor. This *amends MVP FR-022*,
  which fixed the role set at two. The set stays fixed in code and non-configurable; the count
  changes deliberately, because coaching an agent and administering the system are different
  jobs and bundling them to get the first was the wrong trade.
- **FR-038 — chat and existing tickets**: the agent attaches during the conversation. A visitor
  can never reach an existing ticket by naming it, because an email address typed into a
  pre-chat form is not proof of identity. This forced FR-040 (the reference is given at the end,
  not the start) and FR-041 (the placeholder ticket is soft-deleted and audited).
- **FR-039 — availability**: chat is not offered at all when no agent is online. That forced
  FR-042 — anyone already queued when the last agent goes offline is moved to the request form
  rather than left waiting for a closed desk.

**Resolved as documented assumptions** rather than raised as questions, since defensible
defaults exist: agent capacity (three), reconnection grace (60 seconds), idle limit (10 minutes
with a warning at 8), anonymous visitors, one ticket per conversation created up front, no file
transfer during a conversation, and no maximum queue wait.

**Deliberately absent**: WebSocket transport, presence storage, and the chat client's
technology. Those are `/speckit-plan` decisions — ADR-003 left the "htmx over WebSocket or a
Vue component" question open for exactly this phase, and this specification does not pre-empt
it.
