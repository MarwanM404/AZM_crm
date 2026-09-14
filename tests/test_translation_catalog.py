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

import re
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent


#: Every catalog file, in both gettext domains.
#:
#: This used to name `django.po` alone, and that is why "Online" shipped untranslated. The
#: *tool* was taught about `djangojs` when the client-side catalog was added, and this file
#: was not — so `tools/catalog.py status` could see the gap and the test suite could not.
#: CI runs the suite, not the tool, which made the difference invisible where it mattered.
def _all_catalogs():
    from tools.catalog import DOMAINS

    return {
        f"{language}:{domain}": BASE_DIR / "locale" / language / "LC_MESSAGES" / f"{domain}.po"
        for language in ("ar", "en")
        for domain in DOMAINS
        if (BASE_DIR / "locale" / language / "LC_MESSAGES" / f"{domain}.po").exists()
    }


CATALOGS = _all_catalogs()

#: The message domain only, for the checks that are about source strings rather than files.
MESSAGE_CATALOGS = {
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
    # Split by `tools.catalog`, deliberately: that is the parser everything else in this
    # project uses, so it is the one that has to be right. Duplicating the splitting here
    # meant fixing the same blind spot twice — and the copy in this file went on skipping an
    # entry after the tool had stopped.
    from tools.catalog import _blocks

    for block in _blocks(path):
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
    for msgid, translations, _fuzzy in _entries(MESSAGE_CATALOGS["en"]):
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

    entries = _entries(MESSAGE_CATALOGS["ar"])
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


def test_both_gettext_domains_are_checked():
    """The blindness, moved rather than removed (T030).

    Everything in this file used to read `django.po` alone. `djangojs.po` holds the strings
    the browser asks for, and while it was unchecked a wrong client translation would have
    been exactly as invisible as the `Reference` entry was — in a place that now looks
    handled, which is worse.

    Asserted on the tool rather than trusted, because "we remembered the second domain" is
    the kind of thing that stays true only until someone adds a third.
    """
    from tools.catalog import DOMAINS, catalog_paths

    assert set(DOMAINS) == {"django", "djangojs"}

    checked = {path.name for path in catalog_paths("ar")}
    assert checked == {"django.po", "djangojs.po"}, (
        f"the catalog tooling reads {sorted(checked)}; a string in an unread domain is "
        "unchecked and will report as correct"
    )


def test_what_these_checks_cannot_see_is_written_down():
    """FR-021, stated as a limit rather than designed around.

    None of the rules in this file can see a fluent Arabic sentence with the wrong meaning and
    no placeholders. `Reference` was caught because its wrongness was visible in the string
    itself; a plausible mistranslation is not, and only a person reading it will find one.

    This test exists so the limit is recorded where the checks are, rather than assumed away
    by a green run. Human review of meaning is a step in
    specs/003-fix-admin-and-signin/quickstart.md, not an implication of this suite passing.
    """
    from pathlib import Path

    quickstart = (
        Path(__file__).resolve().parent.parent
        / "specs"
        / "003-fix-admin-and-signin"
        / "quickstart.md"
    ).read_text()

    assert "wrong meaning" in quickstart or "reproducing the defect" in quickstart, (
        "the review step that covers what these checks cannot has gone from the validation "
        "scenarios; the suite would then imply a correctness it does not check"
    )


# --- the rule itself, not the catalogs it reads ---
#
# Every check above asks whether the catalogs are correct. None of them asks whether the
# *rule* still works, and the difference is not academic: neutering
# `placeholder_mismatches` to find nothing leaves all of them green, because with the
# catalogs clean "found nothing" and "cannot find anything" produce identical results.
#
# That is the defect this whole feature is about, arrived at from the other direction — a
# check that can only detect absence reporting correctness. These give the rule something it
# must find.


def _catalog(tmp_path, language, body):
    path = tmp_path / language / "LC_MESSAGES"
    path.mkdir(parents=True)
    (path / "django.po").write_text(body, encoding="utf-8")
    return path / "django.po"


def test_the_rule_finds_an_added_placeholder(tmp_path, monkeypatch):
    import tools.catalog as catalog

    _catalog(
        tmp_path,
        "xx",
        'msgid "Reference"\nmsgstr "رد: %(reference)s"\n',
    )
    monkeypatch.setattr(catalog, "LOCALE_DIR", tmp_path)

    found = catalog.placeholder_mismatches("xx")

    assert [(msgid, extra) for msgid, _translated, extra in found] == [
        ("Reference", ["%(reference)s"])
    ]


def test_the_rule_allows_a_translation_that_keeps_its_placeholders(tmp_path, monkeypatch):
    import tools.catalog as catalog

    _catalog(
        tmp_path,
        "xx",
        'msgid "Moved to %(reference)s."\nmsgstr "نُقلت إلى %(reference)s."\n',
    )
    monkeypatch.setattr(catalog, "LOCALE_DIR", tmp_path)

    assert catalog.placeholder_mismatches("xx") == []


def test_the_rule_allows_a_translation_that_drops_one(tmp_path, monkeypatch):
    """Arabic's one and two forms legitimately omit the numeral. A symmetric rule would fail
    five correct entries in the real catalog, and five false positives get a rule deleted."""
    import tools.catalog as catalog

    _catalog(
        tmp_path,
        "xx",
        'msgid "%(counter)s ticket"\nmsgstr "تذكرة واحدة"\n',
    )
    monkeypatch.setattr(catalog, "LOCALE_DIR", tmp_path)

    assert catalog.placeholder_mismatches("xx") == []


def test_the_rule_checks_plural_forms_too(tmp_path, monkeypatch):
    """A mismatch hiding in msgstr[3] is as invisible to a reader of the file as one in
    msgstr, and Arabic has six of them."""
    import tools.catalog as catalog

    _catalog(
        tmp_path,
        "xx",
        'msgid "%(count)d message"\n'
        'msgid_plural "%(count)d messages"\n'
        'msgstr[0] "%(count)d رسالة"\n'
        'msgstr[1] "رسالة واحدة"\n'
        'msgstr[2] "%(count)d رسالة و%(other)s"\n',
    )
    monkeypatch.setattr(catalog, "LOCALE_DIR", tmp_path)

    found = catalog.placeholder_mismatches("xx")

    assert [extra for _msgid, _translated, extra in found] == [["%(other)s"]]


# --- the parser's blind spot (found 2026-09-14) ---
#
# "Online" sat untranslated in djangojs.po for a day while every check here reported both
# catalogs complete. The entry is written immediately after the metadata header with no blank
# line between them, so splitting the file on blank lines puts the header and that entry in
# one block — and every function skips blocks containing "Project-Id-Version".
#
# A malformed file did not make the checks fail. It made them look. That is the same failure
# this project keeps meeting, and this time it was in the tool that was supposed to catch it.


def _msgids_by_naive_scan(path):
    """Every msgid in the file, found without any notion of blocks."""
    return {m for m in re.findall(r'^msgid "(.+)"$', path.read_text(encoding="utf-8"), re.M)}


@pytest.mark.parametrize("language", sorted(CATALOGS))
def test_the_parser_sees_every_entry_in_the_file(language):
    """Two independent readings of the same file, compared.

    A regex scan knows nothing about blocks and cannot be defeated by their absence. If the
    block parser sees fewer entries, the file's structure is hiding some of them — and an
    entry the parser cannot see is an entry no check in this file applies to.
    """
    path = CATALOGS[language]

    naive = _msgids_by_naive_scan(path)
    parsed = {msgid for msgid, _translations, _fuzzy in _entries(path)}
    invisible = naive - parsed

    assert not invisible, (
        f"{path}: these entries are invisible to the parser, so no check in this file "
        f"applies to them: {sorted(invisible)}"
    )
