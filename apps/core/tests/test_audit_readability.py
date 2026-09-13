"""
The audit log can be read (T058-T062, FR-022 to FR-025).

The data has always been complete. It has never been usable: a ticket creation records
sixteen fields as "nothing → value", three of which are reverse relations — `conversations`,
`inbound_logs`, `messages` — that are not fields anybody edited and mean nothing to a reader.
Rows grew tall enough to break the table, and every field name was an internal identifier.

Nothing stored changes here. Audit entries are immutable by requirement (MVP FR-028) and this
is display only, which is also why it cannot lose anything: everything shown before is still
reachable.
"""

import pytest
from auditlog.models import LogEntry

from apps.tickets.models import Ticket

pytestmark = pytest.mark.django_db


@pytest.fixture
def created_ticket(department, branch, category, contact):
    return Ticket.objects.create(
        contact=contact,
        subject="Invoice query",
        description="",
        category=category,
        origin_channel=Ticket.Channel.WEB_FORM,
        department=department,
        branch=branch,
    )


def entry_for(obj, action):
    return LogEntry.objects.filter(object_pk=str(obj.pk), action=action).first()


def readable(entry):
    from apps.core.templatetags.audit import readable_changes

    return readable_changes(entry)


# --- FR-022: a creation is a creation ---


def test_a_creation_is_not_presented_as_every_field_changing(created_ticket):
    entry = entry_for(created_ticket, LogEntry.Action.CREATE)

    assert len(entry.changes_dict) == 16  # what is stored, unchanged
    assert readable(entry) == [], (
        "a creation still lists its fields as having changed from nothing; there was no "
        "previous value to change from"
    )


def test_the_creation_entry_still_says_who_and_when(created_ticket):
    """Nothing is lost by showing less: the actor, the time and the record are on the entry
    itself, not in the change list."""
    entry = entry_for(created_ticket, LogEntry.Action.CREATE)

    assert entry.timestamp is not None
    assert entry.object_repr == created_ticket.reference


# --- FR-023: only what changed ---


def test_a_change_lists_only_the_field_that_moved(created_ticket):
    created_ticket.status = Ticket.Status.OPEN
    created_ticket.save(update_fields=["status"])
    entry = entry_for(created_ticket, LogEntry.Action.UPDATE)

    names = [change.field for change in readable(entry)]

    assert names == ["status"]


def test_it_shows_what_it_moved_from_and_to(created_ticket):
    created_ticket.status = Ticket.Status.OPEN
    created_ticket.save(update_fields=["status"])
    entry = entry_for(created_ticket, LogEntry.Action.UPDATE)

    change = readable(entry)[0]

    assert change.before == "NEW"
    assert change.after == "OPEN"


# --- FR-024: reverse relations and internal identifiers ---


def test_reverse_relations_are_not_listed_as_changed_fields(created_ticket):
    """`conversations`, `inbound_logs` and `messages` are not fields anybody edited. They
    appear because the library records everything on the object, and they mean nothing to
    somebody reading an audit trail."""
    entry = entry_for(created_ticket, LogEntry.Action.CREATE)
    stored = set(entry.changes_dict)
    assert {"conversations", "inbound_logs", "messages"} <= stored

    from apps.core.templatetags.audit import concrete_changes

    shown = {change.field for change in concrete_changes(entry)}

    assert not shown & {"conversations", "inbound_logs", "messages"}


def test_field_names_are_shown_in_the_readers_language(created_ticket):
    from django.utils import translation

    created_ticket.status = Ticket.Status.OPEN
    created_ticket.save(update_fields=["status"])
    entry = entry_for(created_ticket, LogEntry.Action.UPDATE)

    with translation.override("ar"):
        label = readable(entry)[0].label

    assert label == "الحالة", f"the field name reads {label!r} rather than Arabic"


def test_an_unmapped_field_falls_back_to_something_readable(created_ticket):
    """A field nobody has translated must degrade to a readable name, not to a raw identifier
    and not to nothing."""
    from apps.core.templatetags.audit import field_label

    label = str(field_label(Ticket, "first_response_at"))

    assert "_" not in label
    assert label.strip()


def test_an_unknown_field_does_not_crash_the_row(created_ticket):
    """Audit entries outlive schema changes: a field removed from the model still appears in
    entries written before it went. The log must stay readable afterwards."""
    from apps.core.templatetags.audit import field_label

    label = str(field_label(Ticket, "a_field_that_no_longer_exists"))

    assert label.strip()


# --- FR-025 / MVP FR-028: nothing stored is touched ---


def test_rendering_alters_nothing(created_ticket):
    entry = entry_for(created_ticket, LogEntry.Action.CREATE)
    before = entry.changes

    readable(entry)
    entry.refresh_from_db()

    assert entry.changes == before


def test_everything_stored_is_still_reachable(created_ticket):
    """This is display only, so it cannot lose information — the full record is still there
    for anyone who needs it, which is what makes showing less safe."""
    entry = entry_for(created_ticket, LogEntry.Action.CREATE)

    assert len(entry.changes_dict) == 16


def test_a_long_entry_is_bounded_but_not_truncated_away(created_ticket, agent):
    """FR-025. A row that grows without limit breaks the table; one that hides the remainder
    with no way back loses the evidence."""
    from apps.core.templatetags.audit import readable_changes

    created_ticket.subject = "A"
    created_ticket.status = Ticket.Status.OPEN
    created_ticket.priority = Ticket.Priority.HIGH
    created_ticket.description = "B"
    created_ticket.save()
    entry = entry_for(created_ticket, LogEntry.Action.UPDATE)

    changes = readable_changes(entry)

    assert len(changes) == len(
        [f for f in entry.changes_dict if f in {f.name for f in Ticket._meta.fields}]
    ), "the change list drops fields rather than presenting them compactly"


# --- the gap, made detectable rather than fixed once (FR-021, FR-024) ---


def test_every_audited_field_has_a_label():
    """A field with no label renders its internal identifier, in English, in an Arabic log.

    `last_login` did exactly that until somebody opened the page and read it. Mapping the
    thirty-odd fields that existed at the time fixes this instance; this test is what stops
    the next field added to an audited model doing it again — it fails here rather than
    appearing in production as `idle_warned_at`.
    """
    from apps.core.audit import AUDITED_MODELS, EXCLUDED_FIELDS
    from apps.core.templatetags.audit import FIELD_LABELS

    missing = {}
    for model in AUDITED_MODELS:
        excluded = set(EXCLUDED_FIELDS.get(model, []))
        for field in model._meta.fields:
            if field.name in excluded or field.name in FIELD_LABELS:
                continue
            missing.setdefault(field.name, []).append(model.__name__)

    assert not missing, (
        "These audited fields have no label in apps/core/templatetags/audit.py and would "
        "render as internal identifiers: "
        + ", ".join(f"{name} ({', '.join(models)})" for name, models in sorted(missing.items()))
    )


def test_a_field_excluded_from_auditing_needs_no_label():
    """`password` is never recorded (apps/core/audit.py), so demanding a label for it would
    be demanding a translation for a string that cannot appear."""
    from apps.accounts.models import User
    from apps.core.audit import EXCLUDED_FIELDS

    assert "password" in EXCLUDED_FIELDS[User]
