"""
Organization (the customer), Contact, ContactDetail, Note.

A Contact may belong to no Organization (FR-040): the public intake form cannot always
determine an employer. Such contacts surface to staff as needing attention (FR-041). Moving
a contact between organizations is permitted and audited (FR-042); tickets keep their own
organization reference rather than reading through the contact — see apps/tickets/models.py.
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import ScopedSoftDeleteModel


class Organization(ScopedSoftDeleteModel):
    name = models.CharField(_("name"), max_length=200)
    name_ar = models.CharField(_("name (Arabic)"), max_length=200, blank=True)
    reference = models.CharField(max_length=30, unique=True, editable=False)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["reference"],
                condition=models.Q(deleted_at__isnull=True),
                name="unique_organization_reference_when_not_deleted",
            )
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.reference:
            from apps.customers.services.reference import next_organization_reference

            self.reference = next_organization_reference()
        super().save(*args, **kwargs)


class Contact(ScopedSoftDeleteModel):
    """A named person. `organization` is nullable: a contact created from an unrecognized
    intake email starts with no employer (FR-040) until staff link it (FR-041)."""

    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, null=True, blank=True, related_name="contacts"
    )
    full_name = models.CharField(_("full name"), max_length=200)
    preferred_language = models.CharField(
        max_length=2,
        choices=[("ar", _("Arabic")), ("en", _("English"))],
        default="ar",
    )

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name

    @property
    def is_unlinked(self):
        return self.organization_id is None


class ContactDetail(ScopedSoftDeleteModel):
    class Kind(models.TextChoices):
        EMAIL = "EMAIL", _("Email")
        PHONE = "PHONE", _("Phone")

    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name="details")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    value = models.CharField(max_length=255)
    is_primary = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["kind", "value"],
                condition=models.Q(deleted_at__isnull=True),
                name="unique_contact_detail_when_not_deleted",
            )
        ]

    def save(self, *args, **kwargs):
        if self.kind == self.Kind.EMAIL:
            self.value = self.value.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.value


class Note(ScopedSoftDeleteModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    body = models.TextField()

    class Meta:
        ordering = ["-created_at"]
