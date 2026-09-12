# Contract: HTTP endpoints

**Date**: 2026-09-12 | **Plan**: [../plan.md](../plan.md)

The sockets carry the conversation; these carry everything around it. Scope rules are the
MVP's unchanged: an out-of-scope record returns **404, not 403** (MVP FR-024).

## Public

| Method | Path | Access | Returns | Requirement |
|---|---|---|---|---|
| GET | `/chat/availability/` | public | Whether chat is offered at all right now | FR-001, FR-039 |
| GET | `/chat/widget/` | public | The visitor panel, in the visitor's language | FR-001, FR-010 |
| POST | `/chat/start/` | public | Creates the conversation, returns the signed token; **or** the request form when nobody is online | FR-002, FR-039 |
| POST | `/chat/leave-queue/` | public (token) | Removes a waiting visitor | FR-019 |

`/chat/availability/` is deliberately separate and cheap: the public website asks it on every
page load to decide whether to show the chat launcher at all, and it must not become a query
against conversation history.

`/chat/start/` returns the request form rather than a queue when no agent is online (FR-039),
and carries anything already typed into it (FR-018).

## Staff

| Method | Path | Access | Returns | Requirement |
|---|---|---|---|---|
| GET | `/chat/console/` | agent, supervisor | The multi-conversation console | FR-013, FR-015 |
| GET | `/chat/conversations/<id>/` | agent, supervisor, scoped | One conversation with customer context | FR-015 |
| POST | `/chat/conversations/<id>/attach/` | agent, scoped | Re-points to an existing ticket; soft-deletes the placeholder | FR-038, FR-041 |
| GET | `/chat/supervise/` | **supervisor, admin** | Live conversations in scope, available to observe | FR-020 |
| GET | `/chat/supervise/<id>/` | **supervisor, admin**, scoped | The observation view; opens an Observation | FR-020, FR-023 |

## Cross-cutting response rules

1. Out-of-scope conversation: **404**, never 403 (MVP FR-024).
2. An Agent requesting any `/chat/supervise/` path: **403**, and the attempt recorded (FR-037).
3. `/chat/availability/` answers "no" when no agent is online, and the launcher is not shown at
   all (FR-039) — the site must not render a door to a closed room.
4. Every response carries `lang` and `dir` for the active language (MVP FR-032).
5. No customer-facing response ever contains a message with `visibility=INTERNAL`, transcripts
   included (FR-025, MVP FR-015).
