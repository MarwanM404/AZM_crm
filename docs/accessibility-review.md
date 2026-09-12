# Accessibility review

**Date**: 2026-09-12 · **Scope**: every MVP screen, in English and Arabic.

## What is checked automatically

`tests/e2e/test_accessibility.py` runs on every build against a real browser and fails on:

| Check | Why it matters |
|---|---|
| Every form control has an accessible name | A control with only a placeholder is announced as "edit text"; the placeholder also disappears as soon as the user types |
| Exactly one `h1` per page | Screen-reader users navigate by heading level; two or none breaks that |
| Interactive controls are keyboard reachable | A clickable `div` does not exist for keyboard or screen-reader users |
| The focused control shows a visible focus state | Removing the outline without replacing it leaves keyboard users unable to tell where they are |
| The page survives 200% text size | WCAG 1.4.4; a layout pinned to fixed heights clips instead of reflowing |
| The document declares its language | Without `lang`, a screen reader reads Arabic with English pronunciation |

`tests/e2e/test_mobile_layout.py` additionally checks no page scrolls sideways at 390px and
that primary controls are at least 40px tall.

## Found and fixed in this review

- **The queue's search box had no accessible name** — only a placeholder. Given an
  `aria-label`.
- **The public request form's submit button was 21px tall** — it had no button styling at
  all, on the single most important control a customer ever touches. Now 44px.
- **Sign-in's submit button** had the same problem, fixed the same way.

## What automation cannot decide — still needed before release

These require a person and are **not** covered by the suite:

1. **A screen-reader pass** (NVDA or VoiceOver) through the full agent flow in both
   languages, listening for whether the reading order makes sense — not merely whether names
   exist. Arabic in particular needs a native speaker: correct pronunciation depends on
   `lang` being right at the element level, not just the document.
2. **Colour-contrast measurement** against WCAG AA (4.5:1 for body text). The palette was
   chosen to be legible but has not been measured. The status and priority pills are the
   likeliest failures, since they use colour on a tinted background.
3. **Keyboard-only completion of the whole flow** — take a ticket, reply, resolve — without
   touching a mouse, checking that htmx fragment swaps do not strand focus.
4. **Testing with a real user of assistive technology**, which is the only check that finds
   what the others miss.

## Known limitation

The internal-note distinction was explicitly designed for more than colour (amber wash, a
border, a lock icon, and the restriction written out) and is verified under a greyscale
filter in `tests/e2e/test_internal_note_visual.py`. That is the one place colour-blindness was
treated as a first-class constraint rather than an afterthought; the rest of the palette has
not had the same scrutiny, which is what item 2 above is for.
