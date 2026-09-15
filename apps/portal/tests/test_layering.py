"""
T092: the review, written down as a check rather than done once.

A review pass finds what is wrong today. These assert the properties the pass was looking for,
so they keep being true — which matters most for the two that are invisible when broken.

None of this is style. "No ORM in views" is a real boundary here: the customer-facing message
filter lives in one service function, and a view that queries directly is a view that can
reach past it. "No staff filter in the portal" is the same rule stated from the other side.
"""

from pathlib import Path

import pytest

PORTAL = Path(__file__).resolve().parent.parent
PRODUCTION = [p for p in sorted(PORTAL.rglob("*.py")) if "tests" not in p.parts]


def source(path):
    return path.read_text(encoding="utf-8")


def code_lines(path):
    """Lines that are neither blank, comments, nor inside a docstring.

    Needed because half this application's explanation is in prose that names the very things
    these checks forbid — a grep over raw text reports the comment warning against a mistake
    as the mistake.
    """
    lines, in_doc, delimiter = [], False, None
    for raw in source(path).splitlines():
        line = raw.strip()
        if in_doc:
            if delimiter in line:
                in_doc = False
            continue
        if line.startswith(('"""', "'''")):
            delimiter = line[:3]
            if not (line.endswith(delimiter) and len(line) > 3):
                in_doc = True
            continue
        if line.startswith("#") or not line:
            continue
        lines.append(line)
    return lines


def test_no_view_queries_the_database_directly():
    """Reads go through apps/portal/services/tickets.py, which is where the customer-facing
    message filter is applied. A view that queries directly is one that can reach past it."""
    offenders = [
        line
        for line in code_lines(PORTAL / "views.py")
        if ".objects." in line or ".filter(" in line
    ]

    assert not offenders, "views.py queries the database directly:\n" + "\n".join(offenders)


def test_nothing_in_the_portal_uses_the_staff_message_filter():
    """`staff_messages_for` returns internal notes. It has one correct caller in this product
    and it is not here."""
    offenders = [
        f"{path.relative_to(PORTAL)}: {line}"
        for path in PRODUCTION
        for line in code_lines(path)
        if "staff_messages_for" in line
    ]

    assert not offenders, "\n".join(offenders)


def test_nothing_reads_a_ticket_s_messages_without_the_filter():
    """`ticket.messages` is the unfiltered relation. Every customer-facing read goes through
    `public_messages_for`, which is the one place the boundary is written down."""
    offenders = [
        f"{path.relative_to(PORTAL)}: {line}"
        for path in PRODUCTION
        for line in code_lines(path)
        if ".messages.all" in line or ".messages.filter" in line
    ]

    assert not offenders, "\n".join(offenders)


def test_the_portal_does_not_import_the_staff_user_model_to_query_it():
    """It imports `User` twice, both times to REFUSE an address (FR-032). Anything else would
    mean the portal reading the staff table."""
    offenders = [
        f"{path.relative_to(PORTAL)}: {line}"
        for path in PRODUCTION
        for line in code_lines(path)
        if "User.objects" in line and "email__iexact" not in line
    ]

    assert not offenders, "\n".join(offenders)


#: Files that carry a decision. Migrations are generated and `apps.py` is four lines of
#: framework wiring — neither is written by anybody making a choice, and requiring prose
#: there would produce prose that says nothing.
AUTHORED = [
    p
    for p in PRODUCTION
    if p.name not in ("__init__.py", "apps.py") and "migrations" not in p.parts
]


@pytest.mark.parametrize("path", AUTHORED, ids=lambda p: p.name)
def test_every_authored_module_explains_itself(path):
    """Every hand-written file in this application says what it is for.

    Not decoration: this feature's decisions are mostly about what NOT to do — not storing a
    contact link, not reimplementing a state rule, not handing the ticket to the template —
    and an absence explains nothing on its own. Somebody tidying up needs to find the reason
    in the file rather than in a commit message from six months ago.
    """
    text = source(path).lstrip()

    assert text.startswith(('"""', "'''")), f"{path.name} has no module docstring"
