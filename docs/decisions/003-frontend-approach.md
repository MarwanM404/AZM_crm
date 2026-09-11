# ADR-003: Server-rendered Django with htmx and Alpine.js

**Status**: Accepted
**Date**: 2026-09-11
**Roadmap decision**: #3
**Relates to**: [ADR-001](001-web-framework.md)

## Context

The MVP screens are forms, list views, a ticket detail view with a message thread, and a customer
timeline. Two specification requirements dominate the choice:

- FR-031 to FR-035 require Arabic and English across every screen **and** in outbound email, with
  correct right-to-left layout.
- FR-021 and FR-024 require deny-by-default authorization and non-disclosure of records outside the
  acting user's scope.

A separate single-page application was considered and rejected for the MVP.

## Decision

Render the interface from Django templates. Use **htmx** for partial page updates driven by normal
Django views, and **Alpine.js** for small pieces of client-side state such as dropdowns, tabs, and
disclosure toggles. Integrate through `django-htmx`.

Vue.js is not adopted for the MVP. It remains available as a bounded island later, most plausibly
for the live chat widget, where a real component model earns its cost.

## Consequences

**Gained**

- One translation catalog. `gettext` serves both screens and email, so FR-035 does not require a
  second client-side catalog, a second translation review, or a second place for a missing Arabic
  string to hide.
- One authentication model. Session cookies with CSRF protection, so FR-026 needs no token
  revocation list.
- Authorization stays server-side by construction. Every htmx fragment is an ordinary Django view
  with ordinary permission checks, which makes the common single-page failure mode — an endpoint
  returning a full object while the interface hides parts of it — structurally harder to commit
  against FR-024.
- Right-to-left layout is handled in server-rendered HTML with CSS logical properties, avoiding the
  partial right-to-left support common in third-party component libraries.
- No separate build pipeline, no client bundle to version, no API surface to maintain before one is
  actually needed. This is constitution Principle IV applied directly.

**Accepted costs**

- Highly interactive views are less natural than in a component framework. The MVP contains none,
  but live chat does.
- Live chat will need Django Channels for its transport. Whether its client is htmx over WebSocket
  or a small Vue component is deferred to that phase and does not need deciding now.
- Team members experienced in single-page applications will find the fragment model unfamiliar at
  first. This is a short learning curve, not a structural cost.

**Binding conventions**

- CSS uses logical properties (`inline-start`, `inline-end`) rather than `left` and `right`, so
  right-to-left layout follows from the document direction.
- All user-facing strings are externalized from the first commit. No hardcoded display text.
- Every htmx endpoint performs its own authorization check. Being a fragment grants no exemption.

## Alternatives considered

- **Vue single-page application**: rejected for the MVP. It splits the translation catalog in two,
  pushes toward stateless tokens that conflict with FR-026, and adds a REST layer and build pipeline
  that no MVP requirement needs.
- **Inertia.js with Vue**: the strongest alternative. It keeps Django routing, sessions, and
  authentication while allowing Vue components, removing the token problem. Rejected only because
  the translation catalog still splits and the MVP screens do not need components.
- **django-unicorn**: reactive components written in Python. Attractive, but a smaller ecosystem and
  a server round trip per interaction on list views that SC-009 requires to stay responsive at
  50,000 tickets.
- **Plain templates with no library**: sufficient for most MVP screens. htmx is adopted because the
  ticket thread and queue filters genuinely benefit from partial updates, and htmx is roughly 14KB
  with no build step.
