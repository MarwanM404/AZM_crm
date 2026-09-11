"""
Translation-catalog maintenance.

Editing .po files by hand-rolled regex is how this project introduced two rounds of silently
wrong Arabic (see tests/test_translation_catalog.py). This module is the one place that
knows the file format, so the fragility lives here and is tested by that suite.

Usage:
    python tools/catalog.py status              # what is missing or fuzzy, per language
    python tools/catalog.py sync-english        # msgstr = msgid for the source language
    python tools/catalog.py clear-fuzzy ar      # accept guesses you have REVIEWED
"""

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


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "status"
    if command == "status":
        status()
    elif command == "sync-english":
        sync_english()
    elif command == "clear-fuzzy":
        clear_fuzzy(sys.argv[2])
    else:
        print(__doc__)
        sys.exit(1)
