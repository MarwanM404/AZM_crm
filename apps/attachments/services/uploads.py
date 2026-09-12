"""
Attaching files to a message or a note.

One function per parent, both routing through the same validation, so a file arriving from the
public request form is checked exactly as hard as one from an agent — harder, if anything, is
impossible, and softer would be the hole.
"""

from django.core.exceptions import ValidationError

from apps.attachments.models import Attachment
from apps.attachments.services.validation import safe_display_name, validate_upload


def _create(uploaded_file, *, message=None, note=None, uploader, department, branch):
    validate_upload(uploaded_file)
    return Attachment.objects.create(
        message=message,
        note=note,
        file=uploaded_file,
        original_filename=safe_display_name(uploaded_file.name),
        # Recorded for reference only. It is attacker-controlled and is never served back —
        # see apps/attachments/views.py.
        content_type=(uploaded_file.content_type or "")[:100],
        size_bytes=uploaded_file.size,
        uploaded_by=uploader,
        department=department,
        branch=branch,
    )


def attach_to_message(files, message, uploader):
    """Returns (attachments, errors). Errors are per file: one bad file in a set must not
    discard the rest, and the agent needs to know which one was refused."""
    created, errors = [], []
    for uploaded_file in files:
        try:
            created.append(
                _create(
                    uploaded_file,
                    message=message,
                    uploader=uploader,
                    department=message.ticket.department,
                    branch=message.ticket.branch,
                )
            )
        except ValidationError as exc:
            errors.append(f"{safe_display_name(uploaded_file.name)}: {'; '.join(exc.messages)}")
    return created, errors


def attach_to_note(files, note, uploader):
    created, errors = [], []
    for uploaded_file in files:
        try:
            created.append(
                _create(
                    uploaded_file,
                    note=note,
                    uploader=uploader,
                    department=note.department,
                    branch=note.branch,
                )
            )
        except ValidationError as exc:
            errors.append(f"{safe_display_name(uploaded_file.name)}: {'; '.join(exc.messages)}")
    return created, errors
