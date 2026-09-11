"""
FR-031 to FR-035: every screen is bilingual, and RTL layout follows CSS logical properties.

Two checks, both real and running, with known scope limits documented inline rather than
silently assumed:

1. No stylesheet uses `left:`/`right:` as a CSS property (logical properties only), so RTL
   follows document direction automatically.
2. No template renders bare, untranslated user-facing text outside a `{% trans %}` /
   `{% blocktrans %}` tag or a `{{ variable }}`.

The template scanner is line-based and intentionally conservative: it flags a line only when
it finds 2+ consecutive Latin or Arabic letters that survive stripping every Django template
tag, variable, and HTML tag. It will not catch text split across lines or built by string
concatenation in a view; those need a runtime check (T116's Playwright pass) to close.
"""

import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CSS_LEFT_RIGHT = re.compile(r"[{;]\s*(left|right)\s*:", re.IGNORECASE)

# {% blocktrans %}...{% endblocktrans %} wraps its ENTIRE body as translatable content —
# strip the whole block (tags and inner text together), not just the tags, or every
# blocktrans string in the project reads as "untranslated" to this scanner.
BLOCKTRANS_BLOCK = re.compile(r"\{%\s*blocktrans[^%]*%\}.*?\{%\s*endblocktrans\s*%\}", re.DOTALL)
TAG_OR_VAR = re.compile(r"\{%.*?%\}|\{\{.*?\}\}", re.DOTALL)
HTML_TAG = re.compile(r"<[^>]+>")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
LETTERS = re.compile(r"[A-Za-z؀-ۿ]{2,}")

# Attributes and boilerplate that legitimately carry untranslated literal text.
ALLOWED_LINE_SUBSTRINGS = ("DOCTYPE", "charset", "viewport", "csrf_token")


def _css_files():
    return list((BASE_DIR / "static" / "css").glob("*.css"))


def _template_files():
    return list((BASE_DIR / "templates").rglob("*.html"))


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
        text = HTML_COMMENT.sub("", text)
        text = BLOCKTRANS_BLOCK.sub("", text)
        text = TAG_OR_VAR.sub("", text)
        for lineno, line in enumerate(text.splitlines(), start=1):
            if any(marker in line for marker in ALLOWED_LINE_SUBSTRINGS):
                continue
            stripped = HTML_TAG.sub("", line).strip()
            if LETTERS.search(stripped):
                offenders.append(f"{path.relative_to(BASE_DIR)}:{lineno}: {stripped}")
    assert not offenders, "Untranslated text found outside {% trans %}/{{ }}:\n" + "\n".join(
        offenders
    )
