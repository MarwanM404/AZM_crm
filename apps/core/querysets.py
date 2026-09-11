"""
Shared queryset behaviour: soft-delete exclusion and department/branch scoping.

FR-023: every data query MUST be scoped by the acting user's department and branch.
FR-020: soft-deleted rows are hidden from the default manager and remain recoverable.

Callers must call `.for_user(user)` explicitly. There is no implicit, thread-local, or
globally applied filter — ADR-004 rejected that approach because it makes a missed scope
check invisible at the call site. `apps.core.shortcuts.get_object_or_404_for_user` is the
one helper every detail view should route through.
"""

from django.db import models


class CoreQuerySet(models.QuerySet):
    def not_deleted(self):
        return self.filter(deleted_at__isnull=True)

    def for_user(self, user):
        """Scope to the acting user's department and branch. FR-023, FR-024."""
        return self.filter(department=user.department, branch=user.branch)


class SoftDeleteManager(models.Manager.from_queryset(CoreQuerySet)):  # type: ignore[misc]
    """Default manager: excludes soft-deleted rows. Use `all_objects` to see them."""

    def get_queryset(self):
        return super().get_queryset().not_deleted()
