"""
Every quickstart scenario has a test that would fail if it broke (T134).

The twelve scenarios in specs/002-live-chat/quickstart.md are written to be run by a person,
in a browser, in both languages — and they should be, once, before release. This file is the
cheaper guarantee that runs on every commit: for each scenario, the tests that exercise it
exist and are collected.

It is a map, not a substitute. A person running scenario 11 can see that an Arabic sentence
reads awkwardly; nothing here can. What this catches is a scenario quietly losing its coverage
— a test renamed, a file deleted, a feature removed — which is how a validation list becomes
a document nobody trusts.
"""

from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
QUICKSTART = BASE_DIR / "specs" / "002-live-chat" / "quickstart.md"

#: scenario number -> the files that would fail if it stopped working.
COVERAGE = {
    1: ["apps/chat/tests/test_visitor_consumer.py", "tests/e2e/test_two_party_chat.py"],
    2: ["apps/chat/tests/test_typing.py"],
    3: ["apps/chat/tests/test_agent_consumer.py", "apps/chat/tests/test_unread.py"],
    4: ["apps/chat/tests/test_transcript.py", "apps/chat/tests/test_timeline_parity.py"],
    5: ["apps/chat/tests/test_attach_ticket.py"],
    6: [
        "apps/chat/tests/test_supervisor_consumer.py",
        "apps/chat/tests/test_observation_record.py",
    ],
    7: ["tests/test_whisper_isolation.py", "tests/e2e/test_two_party_chat.py"],
    8: ["apps/chat/tests/test_observer_cannot_speak.py"],
    9: [
        "apps/chat/tests/test_desk_closed.py",
        "apps/chat/tests/test_queueing.py",
        "apps/chat/tests/test_last_agent_leaves.py",
    ],
    10: [
        "apps/chat/tests/test_reconnect.py",
        "apps/chat/tests/test_visitor_gone.py",
        "apps/chat/tests/test_agent_gone.py",
    ],
    11: ["tests/e2e/test_rtl_layout.py", "tests/test_translation_catalog.py"],
    12: ["apps/chat/tests/test_deactivated_agent.py"],
}


def _scenario_numbers():
    import re

    return sorted(
        int(match.group(1))
        for match in re.finditer(r"^### (\d+)\. ", QUICKSTART.read_text(), re.M)
    )


def test_every_scenario_in_the_document_is_mapped():
    """A thirteenth scenario added to the quickstart must be claimed by something."""
    unmapped = set(_scenario_numbers()) - set(COVERAGE)

    assert not unmapped, (
        "These quickstart scenarios have no automated coverage recorded. Add the tests that "
        f"would fail if each broke, or record deliberately that none exist: {sorted(unmapped)}"
    )


def test_the_map_does_not_claim_scenarios_that_no_longer_exist():
    stale = set(COVERAGE) - set(_scenario_numbers())

    assert not stale, f"COVERAGE names scenarios not in quickstart.md: {sorted(stale)}"


@pytest.mark.parametrize("scenario", sorted(COVERAGE))
def test_the_tests_named_for_each_scenario_exist(scenario):
    missing = [name for name in COVERAGE[scenario] if not (BASE_DIR / name).exists()]

    assert not missing, (
        f"Scenario {scenario} in quickstart.md is covered by files that no longer exist: "
        f"{missing}"
    )


def test_the_scenarios_are_numbered_without_gaps():
    numbers = _scenario_numbers()

    assert numbers == list(range(1, len(numbers) + 1))
    assert len(numbers) == 12
