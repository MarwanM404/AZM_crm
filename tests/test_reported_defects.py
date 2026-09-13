"""
The five defects reported on 2026-09-13, each reproduced (T001, T002).

Written before anything was fixed, and every one of them failed. The failure messages are
recorded below so a later green run cannot be mistaken for coverage that was always green —
which is exactly what happened to the translation catalog checks, passing for weeks while a
heading rendered a raw placeholder.

Recorded failures from the first run:

1. test_an_account_created_out_of_scope_is_visible_to_its_creator
   AssertionError: the account was created (it is in the database) and is absent from the
   list its creator sees
2. test_an_administrator_without_a_scope_can_see_the_other_accounts
   AssertionError: 2 accounts exist; the list shows only the signed-in one
3. test_no_translation_introduces_a_placeholder_its_source_lacks
   AssertionError: ar: 'Reference' -> 'رد: %(reference)s' introduces %(reference)s
4. test_the_client_side_translation_catalog_is_served
   NoReverseMatch: Reverse for 'javascript-catalog' not found
5. test_an_audit_entry_for_a_creation_does_not_list_every_field
   AssertionError: a created ticket lists 16 changed fields, including reverse relations
   ['conversations', 'inbound_logs', 'messages']

Each test moves to the phase that fixes it. Until then it carries a strict expected-failure
marker naming that phase — strict, so the day the phase lands the marker itself fails and has
to be removed. A defect test that is merely skipped is a defect test nobody notices was fixed.

This file stays afterwards as the record that all five were real.
"""

import re
from pathlib import Path

import pytest
from django.urls import reverse

BASE_DIR = Path(__file__).resolve().parent.parent
PLACEHOLDER = re.compile(r"%\([a-zA-Z_]+\)[sd]|%[sd]|\{[a-zA-Z_]+\}")


# --- 1. An account created out of scope vanishes ---


@pytest.mark.django_db
def test_an_account_created_out_of_scope_is_visible_to_its_creator(
    admin_client_, administrator, other_department, branch, department
):
    """Reported symptom: "the staff account tab only shows the admin account and no created
    accounts". The account IS created — it is simply somewhere its creator cannot look."""
    from apps.accounts.models import User

    admin_client_.post(
        reverse("administration:user_new"),
        {
            "full_name": "Vanishing Agent",
            "email": "vanishing@example.com",
            "role": User.Role.AGENT,
            "department": other_department.pk,
            "branch": branch.pk,
        },
    )
    created = User.objects.filter(email="vanishing@example.com").first()

    body = admin_client_.get(reverse("administration:users")).content.decode()

    assert created is None or "Vanishing Agent" in body, (
        "the account was created (it is in the database) and is absent from the list its "
        "creator sees"
    )


# --- 2. A scopeless administrator sees only itself ---


@pytest.mark.xfail(
    strict=True,
    reason="Open: fixed by User Story 2 (T016-T025). Strict, so this marker fails once it is.",
)
@pytest.mark.django_db
def test_an_administrator_without_a_scope_can_see_the_other_accounts(client, department, branch):
    """The state `createsuperuser` leaves behind, because it never asks for a scope."""
    from apps.accounts.models import User

    root = User.objects.create_superuser(email="root@example.com", password="x", full_name="Root")
    User.objects.create_user(
        email="someone@example.com",
        password="x",
        full_name="Someone Real",
        role=User.Role.AGENT,
        department=department,
        branch=branch,
    )
    client.force_login(root)

    body = client.get(reverse("administration:users")).content.decode()

    assert (
        "Someone Real" in body
    ), f"{User.objects.count()} accounts exist; the list shows only the signed-in one"


# --- 3. A translation that is present, unflagged, and wrong ---


@pytest.mark.parametrize("language", ["ar", "en"])
def test_no_translation_introduces_a_placeholder_its_source_lacks(language):
    """The class of defect the catalog checks could not see. They report completeness and
    uncertainty; a wrong-but-present translation is neither."""
    path = BASE_DIR / "locale" / language / "LC_MESSAGES" / "django.po"
    offenders = []

    for block in path.read_text().split("\n\n"):
        if "Project-Id-Version" in block:
            continue
        ids = re.findall(r'^msgid "(.*)"$', block, re.M)
        strings = re.findall(r'^msgstr(?:\[\d+\])? "(.*)"$', block, re.M)
        if not ids or not strings:
            continue
        allowed = set(PLACEHOLDER.findall(ids[0]))
        for translated in strings:
            extra = set(PLACEHOLDER.findall(translated)) - allowed
            if extra:
                offenders.append(f"{language}: {ids[0]!r} -> {translated!r} adds {sorted(extra)}")

    assert not offenders, "\n  ".join(offenders)


# --- 4. No client-side translations at all ---


@pytest.mark.xfail(
    strict=True,
    reason="Open: fixed by User Story 3 (T034-T035). Strict, so this marker fails once it is.",
)
@pytest.mark.django_db
def test_the_client_side_translation_catalog_is_served(client):
    """`gettextOrFallback` in static/js/chat-console.js looks for a real `gettext` and never
    finds one, so every client string falls back to English."""
    from django.urls import NoReverseMatch

    try:
        url = reverse("javascript-catalog")
    except NoReverseMatch:
        pytest.fail(
            "no client-side translation catalog is routed, so window.gettext does not exist "
            "and every client string falls back to English"
        )

    assert client.get(url).status_code == 200


# --- 5. An audit entry for a creation lists every field ---


@pytest.mark.xfail(
    strict=True,
    reason="Open: fixed by User Story 6 (T058-T068). Strict, so this marker fails once it is.",
)
@pytest.mark.django_db
def test_an_audit_entry_for_a_creation_does_not_list_every_field(
    department, branch, category, contact
):
    """Measured, not estimated: a ticket creation records 16 fields as "nothing -> value",
    including reverse relations that are not fields anyone edited."""
    from auditlog.models import LogEntry

    from apps.tickets.models import Ticket

    ticket = Ticket.objects.create(
        contact=contact,
        subject="S",
        description="",
        category=category,
        origin_channel=Ticket.Channel.WEB_FORM,
        department=department,
        branch=branch,
    )
    entry = LogEntry.objects.filter(object_pk=str(ticket.pk)).first()
    shown = set(entry.changes_dict)
    reverse_relations = {"conversations", "inbound_logs", "messages", "attachments"}

    assert not (shown & reverse_relations), (
        f"a created ticket lists {len(shown)} changed fields, including reverse relations "
        f"{sorted(shown & reverse_relations)}"
    )
