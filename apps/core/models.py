"""
Base model classes every entity in this project composes from.

Constitution: Data Integrity & Auditability requires soft deletion by default and reversible
migrations. FR-020, FR-023, FR-024 are enforced here structurally, not per model.
"""

from django.conf import settings
from django.db import models

from apps.core.querysets import CoreQuerySet, SoftDeleteManager


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteModel(models.Model):
    """Soft deletion by default (FR-020). `objects` hides deleted rows; `all_objects` is the
    explicit escape hatch for administrative recovery and the audit trail."""

    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    objects = SoftDeleteManager()
    all_objects = models.Manager.from_queryset(CoreQuerySet)()

    class Meta:
        abstract = True

    def soft_delete(self, by):
        from django.utils import timezone

        self.deleted_at = timezone.now()
        self.deleted_by = by
        self.save(update_fields=["deleted_at", "deleted_by"])

    @property
    def is_deleted(self):
        return self.deleted_at is not None


class ScopedModel(models.Model):
    """Department/branch scoping (FR-023, FR-024, ADR-004). Set at creation; the object is
    never re-scoped implicitly. `for_user(user)` on the manager applies the filter."""

    department = models.ForeignKey(
        "accounts.Department", on_delete=models.PROTECT, related_name="+"
    )
    branch = models.ForeignKey("accounts.Branch", on_delete=models.PROTECT, related_name="+")

    class Meta:
        abstract = True


class ScopedSoftDeleteModel(TimeStampedModel, SoftDeleteModel, ScopedModel):
    """Convenience base combining the three behaviours every customer-facing entity needs."""

    class Meta:
        abstract = True


# Imported here so Django's app registry discovers it (see apps/core/models_sequence.py).
from apps.core.models_sequence import ReferenceSequence  # noqa: E402,F401
