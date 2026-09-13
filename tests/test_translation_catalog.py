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


# --- the compiled catalogs, not just the source ---
#
# Everything above checks the .po files. Django does not read .po at runtime: it reads the
# compiled .mo, which is a build artifact and is gitignored. So every check above can pass
# while Arabic renders entirely in English, which is what happened in CI — the workflow had
# no `compilemessages` step, and the failure surfaced as three unrelated-looking assertions
# about missing Arabic strings rather than as "the catalogs were never compiled".


COMPILED = {language: path.with_suffix(".mo") for language, path in CATALOGS.items()}


@pytest.mark.parametrize("language", sorted(COMPILED))
def test_the_catalog_is_compiled(language):
    assert COMPILED[language].exists(), (
        f"{COMPILED[language]} is missing. Django reads the compiled .mo, not the .po, so "
        f"every string falls back to English without it. Run `python manage.py "
        f"compilemessages` — and if this failed in CI, the workflow is missing that step."
    )


def test_the_compiled_arabic_catalog_actually_resolves_a_string():
    """Present but stale is as broken as absent, and harder to see."""
    from django.utils import translation

    with translation.override("ar"):
        rendered = translation.gettext("Ticket queue")

    assert rendered != "Ticket queue", (
        "The Arabic catalog compiled but did not translate a string that is present and "
        "non-fuzzy in django.po — the .mo is stale. Re-run `python manage.py compilemessages`."
    )


# --- translations that are present, unflagged, and wrong (T004, T005) ---
#
# Everything above this line asks whether a translation is *there*. `Reference` was there, was
# not fuzzy, and was the Arabic for the email reply subject — so the chat console's heading
# rendered the literal text "رد: %(REFERENCE)S" while this file reported both catalogs clean.
#
# No rule catches a fluent sentence with the wrong meaning. One narrow rule catches the case
# where the wrongness is visible in the string itself, and it is the case that reaches a user
# as obvious breakage rather than as a subtle mistranslation.


@pytest.mark.parametrize("language", sorted(CATALOGS))
def test_no_translation_adds_a_placeholder_its_source_lacks(language):
    from tools.catalog import placeholder_mismatches

    found = placeholder_mismatches(language)

    assert not found, "\n  ".join(
        f"{msgid!r} -> {translated!r} adds {extra}" for msgid, translated, extra in found
    )


def test_a_translation_may_omit_a_placeholder_its_source_has():
    """The rule is one-directional on purpose, and this is the test that keeps it that way.

    Arabic's zero, one and two plural forms legitimately drop the numeral — "رسالة واحدة" is
    "one message" and needs no digit. A symmetric rule would fail five correct entries here,
    and the obvious response to five false positives is to delete the rule.
    """
    from tools.catalog import placeholder_mismatches

    entries = _entries(CATALOGS["ar"])
    omitting = [
        msgid
        for msgid, translations, _fuzzy in entries
        if "%(counter)s" in msgid and any(t and "%(counter)s" not in t for t in translations)
    ]

    assert omitting, "expected at least one Arabic plural form that omits its numeral"

    # Checked against these entries specifically, not against the catalog as a whole: any
    # unrelated mismatch would otherwise make this test fail for somebody else's reason and
    # say nothing about symmetry.
    reported = {msgid for msgid, _translated, _extra in placeholder_mismatches("ar")}
    wrongly_reported = reported & set(omitting)

    assert not wrongly_reported, (
        f"these entries omit a placeholder and were reported as mismatches: "
        f"{sorted(wrongly_reported)}. The rule has become symmetric and will now fail on "
        "correct Arabic plurals."
    )
