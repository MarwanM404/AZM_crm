"""
FR-031 to FR-035: every screen is bilingual, and RTL layout follows CSS logical properties.

Two checks, both real and running:

1. No stylesheet uses `left:`/`right:` as a CSS property (logical properties only), so RTL
   follows document direction automatically.
2. No template renders bare, untranslated user-facing text outside a `{% trans %}` /
   `{% blocktrans %}` tag or a `{{ variable }}`.

The template scanner blanks out everything that is legitimately not translatable copy —
Django comments and tags, blocktrans bodies, and HTML tags *across line boundaries* — while
preserving line numbers, then flags whatever prose survives. Stripping tags per-line (an
earlier version of this test) produced false positives on every multi-line tag, because half
an `<a class="..."` reads as prose once its closing `>` is on the next line.

Known limit: text split across lines or assembled in a view is invisible here; the Playwright
pass in T116 is what closes that.
"""

import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

CSS_LEFT_RIGHT = re.compile(r"[{;]\s*(left|right)\s*:", re.IGNORECASE)

# Deliberately NOT re.DOTALL: Django's {# #} comment is single-line only. A {# that does not
# close on the same line is not a comment to Django at all — it renders the text verbatim.
# Matching multi-line here would make this scanner more permissive than the template engine
# and blind to exactly that bug, which is what shipped a stray comment onto every page.
DJANGO_COMMENT = re.compile(r"\{#[^\n]*?#\}")
UNCLOSED_COMMENT = re.compile(r"\{#(?![^\n]*#\})")
# {% comment %} IS multi-line, unlike {# #} — strip the whole block, body included.
COMMENT_BLOCK = re.compile(r"\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}", re.DOTALL)
# blocktrans wraps its whole body as translatable content — blank the body with the tags.
BLOCKTRANS_BLOCK = re.compile(r"\{%\s*blocktrans[^%]*%\}.*?\{%\s*endblocktrans\s*%\}", re.DOTALL)
TAG_OR_VAR = re.compile(r"\{%.*?%\}|\{\{.*?\}\}", re.DOTALL)
HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
HTML_TAG = re.compile(r"<[^>]*>", re.DOTALL)
LETTERS = re.compile(r"[A-Za-z؀-ۿ]{2,}")

# Language names are always written in their own language — "English" is never translated
# into Arabic, and العربية is never translated into English. That is correct, not a gap.
ALLOWED_LITERALS = {"English", "العربية"}


def _blank_out(pattern, text):
    """Replace each match with as many newlines as it spanned, so line numbers survive."""
    return pattern.sub(lambda m: "\n" * m.group(0).count("\n"), text)


def _css_files():
    return sorted((BASE_DIR / "static" / "css").glob("*.css"))


def _template_files():
    return sorted((BASE_DIR / "templates").rglob("*.html"))


def test_no_css_uses_left_right_properties():
    offenders = []
    for path in _css_files():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if CSS_LEFT_RIGHT.search(line):
                offenders.append(f"{path.relative_to(BASE_DIR)}:{lineno}: {line.strip()}")
    message = "Use logical properties (inline-start/inline-end), not left/right:\n" + "\n".join(
        offenders
    )
    assert not offenders, message


def test_no_untranslated_text_in_templates():
    offenders = []
    for path in _template_files():
        text = path.read_text(encoding="utf-8")
        for pattern in (
            HTML_COMMENT,
            COMMENT_BLOCK,
            DJANGO_COMMENT,
            BLOCKTRANS_BLOCK,
            TAG_OR_VAR,
            HTML_TAG,
        ):
            text = _blank_out(pattern, text)

        for lineno, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped or stripped in ALLOWED_LITERALS:
                continue
            if LETTERS.search(stripped):
                offenders.append(f"{path.relative_to(BASE_DIR)}:{lineno}: {stripped}")

    message = "Untranslated text found outside {% trans %}/{{ }}:\n" + "\n".join(offenders)
    assert not offenders, message


def test_no_multi_line_django_comments():
    """`{# ... #}` is single-line in Django. Spanning two lines does not comment anything —
    the text renders as page content, and in `<head>` the browser hoists it to the top of
    every page. Use `{% comment %}...{% endcomment %}` for anything longer than one line.
    """
    offenders = []
    for path in _template_files():
        text = path.read_text(encoding="utf-8")
        for match in UNCLOSED_COMMENT.finditer(text):
            lineno = text[: match.start()].count("\n") + 1
            snippet = text[match.start() :].split("\n", 1)[0].strip()
            offenders.append(f"{path.relative_to(BASE_DIR)}:{lineno}: {snippet[:80]}")

    message = (
        "These `{# #}` comments do not close on their own line, so Django renders them as "
        "visible text. Use {% comment %}...{% endcomment %}:\n  " + "\n  ".join(offenders)
    )
    assert not offenders, message
