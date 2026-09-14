"""
The sidebar shows you where you are (reported 2026-09-14).

Opening "Unlinked contacts" or "Audit log" left the sidebar highlighting something else —
"Audit log" highlighted "Staff accounts", because the view sets `section` to
"administration" and both administration links test for it.

The template asks `{% if section == 'unlinked' %}` and no view has ever set that. Nothing
connects the two ends but a string, and a string nobody compares is a string that drifts: the
page renders, the link works, and only a reader notices the highlight is on the wrong row.

So there are two tests here. One walks every nav destination and confirms it highlights
itself. The other compares the two ends directly, so a new screen cannot add a section the
nav does not know about, or a nav item nothing ever sets.
"""

import re
from pathlib import Path

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db

SHELL = Path(__file__).resolve().parents[3] / "templates" / "shell.html"

#: Every destination in the sidebar, and who can reach it.
NAV_DESTINATIONS = [
    ("tickets:queue", "agent"),
    ("customers:list", "agent"),
    ("customers:unlinked", "agent"),
    ("chat:console", "agent"),
    ("administration:users", "administrator"),
    ("administration:audit", "administrator"),
]


def highlighted(body):
    """The text of every nav link marked as current."""
    return [
        re.sub(r"<[^>]+>", "", m).strip()
        for m in re.findall(r'<a class="nav__item[^"]*nav__item--on[^"]*"[^>]*>.*?</a>', body, re.S)
    ]


@pytest.mark.parametrize("route,who", NAV_DESTINATIONS)
def test_each_destination_highlights_itself(
    agent_client, admin_client_, department, branch, route, who
):
    client = agent_client if who == "agent" else admin_client_

    body = client.get(reverse(route)).content.decode()
    marked = highlighted(body)

    assert len(marked) == 1, (
        f"{route} highlights {len(marked)} sidebar items: {marked}. Exactly one should be "
        "marked — none leaves the reader without a place, and two is worse than none."
    )


def test_the_audit_log_does_not_highlight_staff_accounts(admin_client_, department, branch):
    """The reported case, kept as its own test so a regression names itself."""
    audit = highlighted(admin_client_.get(reverse("administration:audit")).content.decode())
    users = highlighted(admin_client_.get(reverse("administration:users")).content.decode())

    assert audit != users, f"the audit log and the staff accounts screen both highlight {audit}"


def test_unlinked_contacts_does_not_highlight_customers(agent_client, department, branch):
    unlinked = highlighted(agent_client.get(reverse("customers:unlinked")).content.decode())
    customers = highlighted(agent_client.get(reverse("customers:list")).content.decode())

    assert unlinked != customers


# --- the two ends, compared (so this cannot drift again) ---


def _sections_the_nav_tests_for():
    return set(re.findall(r"section == '([a-z_]+)'", SHELL.read_text()))


def _sections_the_views_set():
    import django.apps

    found = set()
    for config in django.apps.apps.get_app_configs():
        for path in Path(config.path).rglob("views*.py"):
            found |= set(re.findall(r'"section":\s*"([a-z_]+)"', path.read_text()))
    return found


def test_every_nav_item_has_a_view_that_lights_it():
    unreachable = _sections_the_nav_tests_for() - _sections_the_views_set()

    assert not unreachable, (
        "The sidebar tests for these sections and no view sets them, so those items never "
        f"highlight: {sorted(unreachable)}"
    )


def test_every_section_a_view_sets_is_known_to_the_nav():
    unknown = _sections_the_views_set() - _sections_the_nav_tests_for()

    assert not unknown, (
        "These views set a section the sidebar does not test for, so those screens highlight "
        f"nothing: {sorted(unknown)}"
    )
