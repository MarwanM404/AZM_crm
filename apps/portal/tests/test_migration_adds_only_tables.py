"""
T016. The portal's migration creates tables and alters nothing (data-model.md).

data-model.md ends by saying this is the claim to verify rather than trust: "A feature that
says it changes nothing and adds an AlterField has changed something." An AlterField on
`Ticket`, `Message`, `Contact` or `User` would mean the portal had reached into the staff
application's schema, and a schema change is the one kind that is awkward to walk back once
it has been applied to a running database.
"""

import re
from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations"


def test_it_only_creates_models():
    forbidden = re.compile(r"migrations\.(AlterField|RemoveField|AddField|DeleteModel|RenameField)")
    offenders = []

    for migration in sorted(MIGRATIONS.glob("[0-9]*.py")):
        for number, line in enumerate(migration.read_text(encoding="utf-8").splitlines(), 1):
            if forbidden.search(line):
                offenders.append(f"{migration.name}:{number}: {line.strip()}")

    assert not offenders, (
        "The portal's migrations change existing schema rather than only adding tables:\n"
        + "\n".join(offenders)
    )


def test_no_portal_migration_touches_another_app():
    """`run_before`/`dependencies` on another app are fine — that is ordering. Operations
    inside another app's state are not, and `state_operations` is how they get in quietly."""
    for migration in sorted(MIGRATIONS.glob("[0-9]*.py")):
        source = migration.read_text(encoding="utf-8")

        assert "SeparateDatabaseAndState" not in source, (
            f"{migration.name} uses SeparateDatabaseAndState, which can edit another app's "
            "recorded schema without an operation that looks like one."
        )


def test_the_channel_value_changes_no_column():
    """data-model.md: "the migration adds tables and one channel value, and alters no column".

    Adding a value to `Ticket.Channel` makes Django emit an AlterField on two models, which
    looks alarming and is not: `choices` live in Python, and the generated operation changes
    nothing else. What WOULD change a column is a value longer than the field — "PORTAL" is
    six characters against max_length=10 — so the assertion is on max_length staying put
    rather than on the operation being absent.
    """
    import re

    tickets = MIGRATIONS.parent.parent / "tickets" / "migrations"
    latest = sorted(tickets.glob("000[0-9]*alter*channel*.py"))[-1]
    source = latest.read_text(encoding="utf-8")

    lengths = set(re.findall(r"max_length=(\d+)", source))

    assert lengths == {"10"}, (
        f"{latest.name} changes the channel field's max_length to {lengths}. A choices-only "
        "change must leave the column alone."
    )
    assert "PORTAL" in source
    assert "AddField" not in source and "RemoveField" not in source
