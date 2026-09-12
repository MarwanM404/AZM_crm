"""
The only way to read an uploaded file.

MEDIA_ROOT has no URL route, so this view is not a convenience wrapper — it is the access
control. It applies the same scope rule as every other record (404, never 403, per FR-024) and
serves every file as an opaque download so that nothing uploaded can execute in the browser of
the agent who opens it.
"""

from django.http import FileResponse, Http404
from django.utils.encoding import iri_to_uri
from django.views.decorators.http import require_GET

from apps.attachments.models import Attachment
from apps.attachments.services.validation import safe_display_name

# Everything is served as this, whatever was uploaded. The stored content type is
# attacker-controlled; echoing it back is what turns an uploaded file into a rendered page.
SAFE_CONTENT_TYPE = "application/octet-stream"


@require_GET
def download(request, pk):
    attachment = (
        Attachment.objects.for_user(request.user)
        .filter(pk=pk)
        .select_related("message__ticket", "note")
        .first()
    )
    if attachment is None:
        raise Http404

    name = safe_display_name(attachment.original_filename)
    response = FileResponse(
        attachment.file.open("rb"),
        content_type=SAFE_CONTENT_TYPE,
        as_attachment=True,
        filename=name,
    )
    # `as_attachment` sets Content-Disposition; this makes the intent explicit and adds the
    # RFC 5987 form so an Arabic filename survives the trip.
    response.headers["Content-Disposition"] = (
        f'attachment; filename="{name.encode("ascii", "ignore").decode() or "attachment"}"; '
        f"filename*=UTF-8''{iri_to_uri(name)}"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
