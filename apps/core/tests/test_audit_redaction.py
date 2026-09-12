"""
FR-030: credentials and secret material must never reach an audit entry.

This is not hypothetical. django-auditlog audits every field by default, so registering the
User model recorded the password hash — both the old value and the new one — on every
create and every password change. The audit log is deliberately immutable (FR-028), so
anything written there cannot be cleaned out afterwards: an administrator with audit access
would hold an offline-crackable history of every password every user has ever had.
"""

import pytest
from auditlog.models import LogEntry

from apps.accounts.models import User

SENSITIVE_FIELDS = {"password"}


@pytest.mark.django_db
def test_creating_a_user_does_not_audit_the_password(department, branch):
    user = User.objects.create_user(
        email="secret@example.com",
        password="SuperSecret123!",
        full_name="Secret",
        role=User.Role.AGENT,
        department=department,
        branch=branch,
    )
    for entry in LogEntry.objects.get_for_object(user):
        assert not (
            SENSITIVE_FIELDS & set(entry.changes_dict)
        ), f"Audit entry recorded {SENSITIVE_FIELDS & set(entry.changes_dict)} for a user"


@pytest.mark.django_db
def test_changing_a_password_does_not_audit_it(agent):
    agent.set_password("AnotherSecret456!")
    agent.save()

    for entry in LogEntry.objects.get_for_object(agent):
        assert "password" not in entry.changes_dict


@pytest.mark.django_db
def test_no_password_hash_appears_anywhere_in_the_audit_log(department, branch):
    User.objects.create_user(
        email="hash@example.com",
        password="Hunter2Hunter2",
        full_name="Hash",
        role=User.Role.AGENT,
        department=department,
        branch=branch,
    )
    serialized = "".join(str(entry.changes) for entry in LogEntry.objects.all())

    for marker in ("md5$", "pbkdf2_", "argon2", "bcrypt"):
        assert marker not in serialized, f"A {marker} password hash reached the audit log"


@pytest.mark.django_db
def test_ordinary_user_fields_are_still_audited(department, branch):
    """Excluding the password must not blind the trail to everything else (FR-027)."""
    user = User.objects.create_user(
        email="watched@example.com",
        password="pw",
        full_name="Before",
        role=User.Role.AGENT,
        department=department,
        branch=branch,
    )
    user.full_name = "After"
    user.save()

    changes = {}
    for entry in LogEntry.objects.get_for_object(user):
        changes.update(entry.changes_dict)
    assert "full_name" in changes
