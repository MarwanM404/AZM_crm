"""
FR-031: the Arabic catalog must actually be complete.

`tests/test_i18n_completeness.py` checks that templates wrap their strings in {% trans %}.
That is necessary but not sufficient: a string can be correctly marked for translation and
still render in English, in two ways this test exists to catch.

1. An EMPTY msgstr — the string was extracted but never translated.
2. A FUZZY msgstr — `msgmerge` guessed it from a similar string when the catalog was
   regenerated. Django ignores fuzzy entries at runtime and falls back to the English msgid,
   so a fuzzy entry is an untranslated one that merely looks translated in the file. One real
   example from this project: "Contacts" was auto-guessed as جهة الاتصال, the singular.

Both failures are invisible in the interface until an Arabic speaker reads it.
"""

from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
CATALOGS = {
    "ar": BASE_DIR / "locale" / "ar" / "LC_MESSAGES" / "django.po",
    "en": BASE_DIR / "locale" / "en" / "LC_MESSAGES" / "django.po",
}


def _entries(path):
    """Yield (msgid, translations, is_fuzzy) for every real entry.

    gettext wraps a long string as `msgstr ""` followed by continuation lines; those parts
    are ONE translation, not several empty ones. Only `msgstr[N]` lines are separate
    translations (plural forms). Getting this wrong makes every wrapped string look
    untranslated — an earlier version of this test did exactly that.
    """
    blocks = path.read_text(encoding="utf-8").split("\n\n")
    for block in blocks:
        if "Project-Id-Version" in block:
            continue  # the catalog header is always flagged fuzzy; it is not a translation

        lines = block.split("\n")
        fuzzy = any(line.startswith("#, ") and "fuzzy" in line for line in lines)

        msgid_parts: list[str] = []
        plural_forms: list[list[str]] = []
        singular_parts: list[str] = []
        mode = None

        for line in lines:
            if line.startswith("msgid_plural "):
                mode = "skip"
            elif line.startswith("msgid "):
                msgid_parts, mode = [line[6:].strip().strip('"')], "id"
            elif line.startswith("msgstr["):
                plural_forms.append([line.split("]", 1)[1].strip().strip('"')])
                mode = "plural"
            elif line.startswith("msgstr "):
                singular_parts, mode = [line[7:].strip().strip('"')], "single"
            elif line.startswith('"'):
                part = line.strip().strip('"')
                if mode == "id":
                    msgid_parts.append(part)
                elif mode == "single":
                    singular_parts.append(part)
                elif mode == "plural" and plural_forms:
                    plural_forms[-1].append(part)

        msgid = "".join(msgid_parts)
        if not msgid:
            continue

        if plural_forms:
            translations = ["".join(form) for form in plural_forms]
        else:
            translations = ["".join(singular_parts)]

        yield msgid, translations, fuzzy


@pytest.mark.parametrize("language", sorted(CATALOGS))
def test_no_untranslated_strings(language):
    path = CATALOGS[language]
    missing = [mid for mid, translations, _ in _entries(path) if not all(translations)]
    assert not missing, (
        f"{len(missing)} string(s) have no {language} translation:\n  " + "\n  ".join(missing[:20])
    )


@pytest.mark.parametrize("language", sorted(CATALOGS))
def test_no_fuzzy_translations(language):
    """Django silently ignores fuzzy entries, so they render in English."""
    path = CATALOGS[language]
    fuzzy = [mid for mid, _t, is_fuzzy in _entries(path) if is_fuzzy]
    assert not fuzzy, (
        f"{len(fuzzy)} {language} translation(s) are marked fuzzy and will render in English. "
        "Review each, correct it, and remove the '#, fuzzy' flag:\n  " + "\n  ".join(fuzzy[:20])
    )


@pytest.mark.parametrize("language", sorted(CATALOGS))
def test_plural_forms_are_all_filled(language):
    """Arabic declares six plural forms; a partially filled set renders English for the
    missing cases only, which is the hardest kind of gap to notice."""
    path = CATALOGS[language]
    incomplete = [
        mid
        for mid, translations, _ in _entries(path)
        if len(translations) > 1 and not all(translations)
    ]
    assert not incomplete, f"Incomplete plural forms: {incomplete}"


def test_english_catalog_matches_its_own_source_strings():
    """English is the source language, so every msgstr must be its own msgid.

    This is not busywork. `msgmerge` fills a regenerated catalog by guessing from similar
    strings and flags the guesses fuzzy; clearing those flags without checking the values
    makes Django start serving the wrong English string. That happened in this project: an
    empty customer timeline rendered "No messages on this ticket yet." and the contact filter
    rendered "Contact" instead of "All contacts". A mismatch here is always a bug.
    """
    mismatches = []
    for msgid, translations, _fuzzy in _entries(CATALOGS["en"]):
        if len(translations) == 1 and translations[0] and translations[0] != msgid:
            mismatches.append(f"{msgid!r} -> {translations[0]!r}")

    assert not mismatches, (
        "English translations that do not match their source string:\n  "
        + "\n  ".join(mismatches[:20])
    )
