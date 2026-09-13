"""
Translation-catalog maintenance.

Editing .po files by hand-rolled regex is how this project introduced two rounds of silently
wrong Arabic (see tests/test_translation_catalog.py). This module is the one place that
knows the file format, so the fragility lives here and is tested by that suite.

Usage:
    python tools/catalog.py status              # what is missing or fuzzy, per language
    python tools/catalog.py sync-english        # msgstr = msgid for the source language
    python tools/catalog.py clear-fuzzy ar      # accept guesses you have REVIEWED
    python tools/catalog.py fill ar < map.json  # apply reviewed translations
    python tools/catalog.py placeholders        # translations that add a placeholder
"""

import json
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LOCALE_DIR = BASE_DIR / "locale"

# The flag line can carry more than one flag: "#, fuzzy, python-format".
FUZZY_LINE = re.compile(r"^#,.*\bfuzzy\b.*$\n?", re.MULTILINE)
# gettext records what it merged FROM as "#| msgid ...". Once the guess is accepted or
# corrected that record is stale, so it goes with the flag.
PREVIOUS_MSGID_LINE = re.compile(r"^#\|.*$\n?", re.MULTILINE)

# %(name)s, %(count)d, %s, %d, {name} — every substitution form this project uses.
PLACEHOLDER = re.compile(r"%\([a-zA-Z_]+\)[sd]|%[sd]|\{[a-zA-Z_]+\}")


def catalog_path(language):
    return LOCALE_DIR / language / "LC_MESSAGES" / "django.po"


def _blocks(path):
    return path.read_text(encoding="utf-8").split("\n\n")


def _write(path, blocks):
    path.write_text("\n\n".join(blocks), encoding="utf-8")


def _string_parts(lines, start_keyword):
    """Collect a possibly wrapped gettext string beginning at `start_keyword`."""
    parts, collecting = [], False
    for line in lines:
        if line.startswith(start_keyword):
            parts = [line[len(start_keyword) :].strip().strip('"')]
            collecting = True
        elif collecting and line.startswith('"'):
            parts.append(line.strip().strip('"'))
        elif collecting:
            break
    return "".join(parts)


def status():
    for language in sorted(p.name for p in LOCALE_DIR.iterdir() if p.is_dir()):
        path = catalog_path(language)
        if not path.exists():
            continue
        missing, fuzzy = [], []
        for block in _blocks(path):
            if "Project-Id-Version" in block:
                continue
            lines = block.split("\n")
            msgid = _string_parts(lines, "msgid ")
            if not msgid:
                continue
            if FUZZY_LINE.search(block):
                fuzzy.append(msgid)
            singular = _string_parts(lines, "msgstr ")
            plurals = [line for line in lines if line.startswith("msgstr[")]
            if plurals:
                if any(line.split("]", 1)[1].strip() == '""' for line in plurals):
                    missing.append(msgid)
            elif not singular:
                missing.append(msgid)
        print(f"{language}: {len(missing)} untranslated, {len(fuzzy)} fuzzy")
        for m in missing:
            print(f"   missing: {m[:90]}")
        for f in fuzzy:
            print(f"   fuzzy:   {f[:90]}")


def placeholder_mismatches(language):
    """Translations containing a placeholder their source string does not have.

    The rule is deliberately one-directional, and the asymmetry is the whole finding. An
    *extra* placeholder is always a bug: nothing will substitute it, so the reader sees the
    raw code. A *missing* one usually is not — Arabic's zero, one and two plural forms
    legitimately drop the numeral ("رسالة واحدة" is "one message", with no digit), and five
    correct entries in this catalog would fail a symmetric rule.

    This is the class the other checks cannot see. `status` reports what is absent and what is
    uncertain; an entry that is present, unflagged and wrong is neither. It reported both
    catalogs clean while the chat console heading rendered the literal text
    "رد: %(REFERENCE)S" — the Arabic for the email reply subject, attached to the word
    "Reference".

    What it does NOT catch, stated rather than designed around: a fluent sentence with the
    wrong meaning and no placeholders passes. Only a person reading it will find that.
    """
    path = catalog_path(language)
    if not path.exists():
        return []

    found = []
    for block in _blocks(path):
        if "Project-Id-Version" in block:
            continue
        lines = block.split("\n")
        msgid = _string_parts(lines, "msgid ")
        if not msgid:
            continue

        allowed = set(PLACEHOLDER.findall(msgid))
        plural_id = _string_parts(lines, "msgid_plural ")
        if plural_id:
            allowed |= set(PLACEHOLDER.findall(plural_id))

        translations = [_string_parts(lines, "msgstr ")]
        translations += [
            line.split("]", 1)[1].strip().strip('"') for line in lines if line.startswith("msgstr[")
        ]
        for translated in translations:
            if not translated:
                continue
            extra = sorted(set(PLACEHOLDER.findall(translated)) - allowed)
            if extra:
                found.append((msgid, translated, extra))
    return found


def placeholders():
    """Report placeholder mismatches for every language. Non-zero exit when any are found."""
    total = 0
    for language in sorted(p.name for p in LOCALE_DIR.iterdir() if p.is_dir()):
        found = placeholder_mismatches(language)
        total += len(found)
        print(f"{language}: {len(found)} placeholder mismatch(es)")
        for msgid, translated, extra in found:
            print(f"   {msgid[:60]!r}")
            print(f"      -> {translated[:60]!r} adds {extra}")
    return total


def sync_english():
    """English is the source language, so every msgstr is its own msgid. Provably correct,
    and it removes the class of bug where a guessed English string ships."""
    path = catalog_path("en")
    out, changed = [], 0
    for block in _blocks(path):
        if "Project-Id-Version" in block:
            out.append(block)
            continue
        original = block
        block = PREVIOUS_MSGID_LINE.sub("", FUZZY_LINE.sub("", block))
        lines = block.split("\n")

        if any(line.startswith("msgid_plural") for line in lines):
            singular = _string_parts(lines, "msgid ")
            plural = _string_parts(lines, "msgid_plural ")
            block = re.sub(r'msgstr\[0\] ".*"', f'msgstr[0] "{singular}"', block)
            block = re.sub(r'msgstr\[1\] ".*"', f'msgstr[1] "{plural}"', block)
        else:
            msgstr_at = next((i for i, line in enumerate(lines) if line.startswith("msgstr")), None)
            msgid_at = next((i for i, line in enumerate(lines) if line.startswith("msgid ")), None)
            if msgstr_at is not None and msgid_at is not None:
                msgid_lines = [lines[msgid_at][len("msgid ") :]]
                for line in lines[msgid_at + 1 : msgstr_at]:
                    if line.startswith('"'):
                        msgid_lines.append(line)
                block = "\n".join(
                    lines[:msgstr_at] + ["msgstr " + msgid_lines[0]] + msgid_lines[1:]
                )
        if block != original:
            changed += 1
        out.append(block)
    _write(path, out)
    print(f"english: {changed} entries synced to their source strings")


def clear_fuzzy(language):
    """Accept guesses you have ALREADY reviewed. Never run this blind: Django ignores fuzzy
    entries, so clearing a flag is what makes a wrong guess start shipping."""
    path = catalog_path(language)
    out = []
    for block in _blocks(path):
        if "Project-Id-Version" not in block:
            block = PREVIOUS_MSGID_LINE.sub("", FUZZY_LINE.sub("", block))
        out.append(block)
    _write(path, out)
    print(f"{language}: fuzzy flags cleared")


def fill(language, translations):
    """Apply a reviewed {msgid: msgstr} mapping, clearing the fuzzy flag on anything it
    touches. Handles gettext's wrapped form, which is where hand-rolled regex kept failing."""
    path = catalog_path(language)
    out, applied = [], 0
    for block in _blocks(path):
        if "Project-Id-Version" in block:
            out.append(block)
            continue
        lines = block.split("\n")
        msgid = _string_parts(lines, "msgid ")
        if msgid in translations:
            value = translations[msgid].replace("\\", "\\\\").replace('"', '\\"')
            msgstr_at = next((i for i, line in enumerate(lines) if line.startswith("msgstr")), None)
            if msgstr_at is not None:
                head = [
                    line
                    for line in lines[:msgstr_at]
                    if not line.startswith("#,") and not line.startswith("#|")
                ]
                block = "\n".join(head + [f'msgstr "{value}"'])
                applied += 1
        out.append(block)
    _write(path, out)
    print(f"{language}: {applied} translation(s) applied")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "status"
    if command == "status":
        status()
    elif command == "sync-english":
        sync_english()
    elif command == "clear-fuzzy":
        clear_fuzzy(sys.argv[2])
    elif command == "fill":
        fill(sys.argv[2], json.load(sys.stdin))
    elif command == "placeholders":
        sys.exit(1 if placeholders() else 0)
    else:
        print(__doc__)
        sys.exit(1)
