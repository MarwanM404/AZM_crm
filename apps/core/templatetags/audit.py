"""
Making an audit entry readable (FR-022 to FR-025).

The stored data is complete and untouched by anything here — entries are immutable by
requirement (MVP FR-028), and this module only decides what to show. That is also why showing
less is safe: nothing is lost, because nothing is changed.

Three things were wrong with showing all of it.

A **creation** was rendered as sixteen fields changing from nothing, which is true and useless:
there was no previous value to change from, and the interesting fact is simply that the record
was created. A creation now shows no change list at all.

**Reverse relations** — `conversations`, `inbound_logs`, `messages` — appeared as changed
fields. Nobody edited them; they are on the object because the library records everything it
finds, and they mean nothing to somebody reading an audit trail.

**Field names** were internal identifiers. `origin_channel` is not what a reader calls it, and
in Arabic it was not even English.
"""

from dataclasses import dataclass

from django import template
from django.utils.translation import gettext_lazy as _

register = template.Library()

#: Field names that appear across audited models, in the reader's language.
#:
#: A map rather than the models' own `verbose_name`, because almost none of them declare a
#: translatable one and adding thirty of them is a migration per model for a display concern.
#: Keyed by field name rather than by model: `status`, `subject` and `created_at` mean the same
#: thing wherever they appear, and a per-model map would be thirty copies of the same word.
#:
#: Anything unmapped falls back to a humanised version of the name, so a new field degrades to
#: something readable rather than to a raw identifier or to nothing.
FIELD_LABELS = {
    # The customer portal (spec 004). An administrator reading the audit log should see what
    # happened to somebody's account without knowing the portal's column names — which is the
    # whole point of this table, and the reason registering a model for auditing without
    # labelling its fields fails the build.
    "account": _("customer account"),
    "email_confirmed_at": _("email address confirmed"),
    "expires_at": _("link expires"),
    "purpose": _("link purpose"),
    "used_at": _("link used"),
    "assigned_to": _("assigned to"),
    "branch": _("branch"),
    "category": _("category"),
    "contact": _("contact"),
    "created_at": _("created"),
    "deleted_at": _("deleted"),
    "deleted_by": _("deleted by"),
    "department": _("department"),
    "description": _("description"),
    "email": _("email"),
    "ended_at": _("ended"),
    "end_reason": _("reason for ending"),
    "full_name": _("full name"),
    "is_active": _("active"),
    "language": _("language"),
    "name": _("name"),
    "organization": _("organization"),
    "origin_channel": _("channel"),
    "priority": _("priority"),
    "reference": _("reference"),
    "resolved_at": _("resolved"),
    "role": _("role"),
    "state": _("state"),
    "status": _("status"),
    "subject": _("subject"),
    "ticket": _("ticket"),
    "updated_at": _("updated"),
    "visibility": _("visibility"),
    # The rest of the audited models' fields. Completeness is enforced by
    # apps/core/tests/test_audit_readability.py rather than remembered: a new field on an
    # audited model fails that test instead of quietly rendering an English identifier in an
    # Arabic log, which is how `last_login` was found here.
    "assigned_at": _("assigned"),
    "author": _("author"),
    "body": _("message"),
    "channel": _("channel"),
    "content_type": _("record type"),
    "conversation": _("conversation"),
    "delivery_error": _("delivery error"),
    "delivery_status": _("delivery status"),
    "direction": _("direction"),
    "ended_by": _("ended by"),
    "external_id": _("external identifier"),
    "file": _("file"),
    "first_response_at": _("first response"),
    "id": _("identifier"),
    "idle_warned_at": _("idle warning sent"),
    "is_primary": _("primary"),
    "is_staff": _("staff access"),
    "is_superuser": _("superuser"),
    "kind": _("kind"),
    "last_activity_at": _("last activity"),
    "last_login": _("last signed in"),
    "message": _("message"),
    "name_ar": _("name (Arabic)"),
    "note": _("note"),
    "observer": _("observer"),
    "original_filename": _("file name"),
    "preferred_language": _("preferred language"),
    "size_bytes": _("size"),
    "started_at": _("started"),
    "uploaded_by": _("uploaded by"),
    "value": _("value"),
    "visitor_token_hash": _("visitor token"),
}


@dataclass(frozen=True)
class Change:
    field: str
    label: str
    before: str
    after: str


def field_label(model, name):
    """What to call this field to a reader.

    Falls back twice rather than once. An unmapped field becomes its humanised name, and a
    field that no longer exists on the model becomes the same — audit entries outlive schema
    changes, so a field removed last month is still named in entries written before it went,
    and the log has to stay readable afterwards.
    """
    if name in FIELD_LABELS:
        return FIELD_LABELS[name]
    return name.replace("_", " ")


def _concrete_field_names(model):
    """Fields that exist on the record itself. Reverse relations are not among them."""
    return {field.name for field in model._meta.fields}


def concrete_changes(entry):
    """Every stored change that is a real field of the model, in a stable order."""
    model = entry.content_type.model_class()
    if model is None:
        # The model is gone but the entry remains — immutability means old entries outlive
        # the code that wrote them. Show what is there rather than nothing.
        return [
            Change(name, name.replace("_", " "), str(before), str(after))
            for name, (before, after) in sorted(entry.changes_dict.items())
        ]

    concrete = _concrete_field_names(model)
    return [
        # str() now, not later. `gettext_lazy` resolves when the value is finally used, and
        # "finally used" for a template filter is after the request's language has gone —
        # so a lazy label renders in whatever language happens to be active at that moment.
        Change(name, str(field_label(model, name)), str(before), str(after))
        for name, (before, after) in sorted(entry.changes_dict.items())
        if name in concrete
    ]


@register.filter
def readable_changes(entry):
    """What to show for this entry. Empty for a creation (FR-022)."""
    from auditlog.models import LogEntry

    if entry.action == LogEntry.Action.CREATE:
        return []
    return concrete_changes(entry)


#: What happened, in the reader's language. The library's own labels are English, and
#: `create` / `update` / `delete` are the three words a reader scans this column for.
ACTION_LABELS = {
    0: _("created"),
    1: _("changed"),
    2: _("deleted"),
    3: _("accessed"),
}


@register.filter
def action_label(entry):
    return ACTION_LABELS.get(entry.action, entry.get_action_display())
