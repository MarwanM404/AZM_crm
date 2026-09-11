"""
Centralized audit registration (T030).

Every model FR-027 requires an audit trail for is registered here, in one place. This
includes every SoftDeleteModel subclass (Organization, Contact, ContactDetail, Note,
Category, Ticket, Message) plus User, Department, and Branch, which are audited without
being soft-deletable (accounts are deactivated, not deleted; FR-026).
tests/test_audit_coverage.py discovers every SoftDeleteModel subclass via introspection and
asserts each one appears in AUDITED_MODELS, so a new soft-deletable model cannot silently
skip FR-027 by being forgotten here.

django-auditlog stores actor, UTC timestamp, and a before/after diff of changed fields per
entry (FR-027), and is registered read-only in the admin so no role can edit or delete an
entry (FR-028). See apps/core/admin.py.
"""

from auditlog.registry import auditlog

from apps.accounts.models import Branch, Department, User
from apps.customers.models import Contact, ContactDetail, Note, Organization
from apps.tickets.models import Category, Message, Ticket

AUDITED_MODELS = [
    Organization,
    Contact,
    ContactDetail,
    Note,
    Category,
    Ticket,
    Message,
    User,
    Department,
    Branch,
]


def register_all():
    for model in AUDITED_MODELS:
        if not auditlog.contains(model):
            auditlog.register(model)
