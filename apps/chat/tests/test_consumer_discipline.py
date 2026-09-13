"""
Consumers do transport and nothing else (T130).

Two rules, both from apps/chat/consumers/base.py, and both easy to break in a way that
neither review nor the rest of the suite would notice.

**Every database touch goes through `database_sync_to_async`.** The ORM is synchronous; a
query issued directly from an async consumer blocks the event loop serving every other socket
on that worker. It does not error, it does not appear in a test, and it does not show up until
the desk is busy — which is the only time it matters.

**Every decision about who may see what is made in services/.** A consumer that picks its own
group or filters its own messages moves the one boundary that must not be got wrong into three
places that each look reasonable on their own.

Asserted by reading the source, because both failures are invisible at runtime in a suite
where one socket is open at a time.
"""

import ast
from pathlib import Path

import pytest

CONSUMERS = sorted((Path(__file__).resolve().parents[1] / "consumers").glob("*.py"))

#: Names that reach the database. `objects` catches every manager call in one word.
ORM_MARKERS = ("objects", "select_for_update", "atomic")


def _sync_wrapped_functions(tree):
    """Functions carrying @database_sync_to_async, plus every function they define inside."""
    wrapped = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in node.decorator_list:
                name = getattr(decorator, "id", None) or getattr(decorator, "attr", None)
                if name == "database_sync_to_async":
                    wrapped.add(node)
    return wrapped


@pytest.mark.parametrize("path", CONSUMERS, ids=lambda p: p.name)
def test_no_orm_access_outside_database_sync_to_async(path):
    tree = ast.parse(path.read_text())
    safe = _sync_wrapped_functions(tree)
    safe_lines = {
        line for node in safe for line in range(node.lineno, (node.end_lineno or node.lineno) + 1)
    }

    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute) or node.attr not in ORM_MARKERS:
            continue
        if node.lineno in safe_lines:
            continue
        offenders.append(f"{path.name}:{node.lineno} .{node.attr}")

    assert not offenders, (
        "These reach the database from async code, blocking the event loop for every other "
        "socket on the worker. Move the call into a @database_sync_to_async method:\n  "
        + "\n  ".join(offenders)
    )


@pytest.mark.parametrize("path", CONSUMERS, ids=lambda p: p.name)
def test_consumers_do_not_decide_visibility_for_themselves(path):
    """Group choice and message filtering belong to services/, in one place.

    Consumers may *join* the groups their own socket belongs to — that is transport. What they
    may not do is decide, per message, who should receive it.
    """
    source = path.read_text()

    forbidden = {
        "Visibility.INTERNAL": "filters on visibility; apps/chat/services/messaging.py owns "
        "that decision",
        "public_messages_for": "chooses a customer-facing filter; a service should have "
        "chosen it already",
        "staff_messages_for": "chooses a staff filter; a service should have chosen it " "already",
    }
    found = [f"{path.name}: {why}" for token, why in forbidden.items() if token in source]

    assert not found, "\n  ".join(found)


def test_the_supervisor_consumer_still_has_no_route_to_the_customer():
    """Restated here as well as in the whisper tests, because this file is where someone
    tidying the consumers will look."""
    source = (Path(__file__).resolve().parents[1] / "consumers" / "supervisor.py").read_text()

    assert "public_group" not in source
    assert "agent_message" not in source
