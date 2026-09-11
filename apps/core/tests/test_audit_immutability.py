"""FR-028: audit entries are immutable to every role, including administrators."""

import pytest
from auditlog.models import LogEntry
from django.urls import reverse

from apps.core.admin import AuditLogEntryAdmin


@pytest.mark.django_db
def test_admin_registration_forbids_add_change_and_delete(rf, administrator):
    from django.contrib import admin as django_admin

    model_admin = AuditLogEntryAdmin(LogEntry, django_admin.site)
    request = rf.get("/")
    request.user = administrator

    assert model_admin.has_add_permission(request) is False
    assert model_admin.has_change_permission(request) is False
    assert model_admin.has_delete_permission(request) is False


@pytest.mark.django_db
def test_superuser_cannot_delete_an_entry_through_django_admin(client, department, branch):
    """Django's ModelAdmin always registers add/change/delete URLs; the permission methods
    are what decide reachability, so the route existing proves nothing either way. This
    attempts the deletion as the most privileged actor there is and asserts refusal — the
    property FR-028 actually requires."""
    from apps.accounts.models import User

    superuser = User.objects.create_superuser(
        email="root@example.com",
        password="pw",
        full_name="Root",
        department=department,
        branch=branch,
    )
    client.force_login(superuser)

    from apps.customers.models import Organization

    Organization.objects.create(name="Audited", department=department, branch=branch)
    entry = LogEntry.objects.first()
    assert entry is not None, "no audit entry to attempt deleting"

    response = client.post(
        reverse("admin:auditlog_logentry_delete", args=[entry.pk]), {"post": "yes"}
    )
    assert response.status_code in (403, 302)
    assert LogEntry.objects.filter(pk=entry.pk).exists(), "the audit entry was deleted"


@pytest.mark.django_db
def test_superuser_cannot_change_an_entry_through_django_admin(client, department, branch):
    from apps.accounts.models import User

    superuser = User.objects.create_superuser(
        email="root2@example.com",
        password="pw",
        full_name="Root Two",
        department=department,
        branch=branch,
    )
    client.force_login(superuser)

    from apps.customers.models import Organization

    Organization.objects.create(name="Audited", department=department, branch=branch)
    entry = LogEntry.objects.first()
    response = client.post(
        reverse("admin:auditlog_logentry_change", args=[entry.pk]), {"object_repr": "tampered"}
    )
    assert response.status_code in (403, 302)

    entry.refresh_from_db()
    assert entry.object_repr != "tampered"


@pytest.mark.django_db
def test_our_own_audit_screen_exposes_no_write_route():
    """Our administration URLs carry exactly one audit route, and it is a read."""
    from django.urls import URLPattern, URLResolver, get_resolver

    names = []

    def walk(resolver, namespace=None):
        for entry in resolver.url_patterns:
            if isinstance(entry, URLResolver):
                walk(entry, entry.namespace or namespace)
            elif isinstance(entry, URLPattern) and entry.name and namespace == "administration":
                names.append(entry.name)

    walk(get_resolver())
    audit_routes = [n for n in names if "audit" in n]
    assert audit_routes == ["audit"], f"unexpected audit routes: {audit_routes}"


@pytest.mark.django_db
def test_audit_screen_is_administrator_only(agent_client, admin_client_):
    assert agent_client.get(reverse("administration:audit")).status_code == 403
    assert admin_client_.get(reverse("administration:audit")).status_code == 200
