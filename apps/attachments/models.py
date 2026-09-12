"""
File attachments on ticket messages and customer notes.

Storage rules, each guarding a specific failure:

- The stored path is generated, never the uploaded filename. A filename is attacker-controlled
  input and `../../etc/passwd` is a path, not a name. The original is kept for display only.
- Files live under MEDIA_ROOT, which has no URL route at all. The only way to read one is
  `apps.attachments.views.download`, which applies the same scope check as every other record
  (FR-023, FR-024) and the internal-visibility rule (FR-015).
- The content type is recorded but never trusted on the way back out: the download view serves
  a safe type with `Content-Disposition: attachment`, so an uploaded .html or .svg is
  downloaded rather than executed in an agent's browser.
"""

import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import ScopedSoftDeleteModel


def attachment_path(instance, filename):
    """A generated path. The uploaded name is never part of it — see the module docstring."""
    suffix = Path(filename).suffix.lower()[:10]  # for humans reading the directory only
    return f"attachments/{uuid.uuid4().hex[:2]}/{uuid.uuid4().hex}{suffix}"


class Attachment(ScopedSoftDeleteModel):
    """Belongs to exactly one of a ticket message or a customer note."""

    message = models.ForeignKey(
        "tickets.Message",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    note = models.ForeignKey(
        "customers.Note",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="attachments",
    )

    file = models.FileField(upload_to=attachment_path)
    original_filename = models.CharField(_("file name"), max_length=255)
    content_type = models.CharField(max_length=100)
    size_bytes = models.PositiveIntegerField()
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(message__isnull=False, note__isnull=True)
                    | models.Q(message__isnull=True, note__isnull=False)
                ),
                name="attachment_belongs_to_exactly_one_parent",
            )
        ]

    def __str__(self):
        return self.original_filename

    def clean(self):
        if bool(self.message_id) == bool(self.note_id):
            raise ValidationError(
                _("An attachment must belong to either a message or a note, not both.")
            )

    @property
    def is_internal(self):
        """True when this file hangs off an internal message or a customer note.

        Notes are staff-only by definition, and a file on an internal message inherits that
        message's visibility — otherwise the attachment becomes a way around FR-015 that the
        message-level filter never sees.
        """
        if self.note_id:
            return True
        from apps.tickets.models import Message

        return self.message.visibility == Message.Visibility.INTERNAL
