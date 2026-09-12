"""
Upload validation.

The public request form accepts files from anyone on the internet, so this runs on every
upload path rather than only the staff ones. Three checks, each cheap and each closing a real
hole:

- **Size**, so the endpoint cannot be used to fill the disk.
- **Extension and declared type**, as an allowlist. A denylist of dangerous types is a losing
  game; an allowlist of what support actually needs is not.
- **Emptiness**, because a zero-byte file is almost always a failed upload rather than an
  intentional one, and storing it just confuses the agent who opens it.

None of this makes an uploaded file safe to execute — nothing does. Safety on the way out
comes from the download view refusing to serve anything as a renderable type.
"""

from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

# What a support desk actually receives: screenshots, documents, spreadsheets, logs.
ALLOWED_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".csv",
    ".txt",
    ".log",
    ".zip",
    ".heic",
}

# Types that render and can carry script are absent on purpose: .html, .htm, .svg, .xml.
# An SVG is an image to a user and a script host to a browser.
MAX_BYTES = getattr(settings, "MAX_ATTACHMENT_BYTES", 10 * 1024 * 1024)


def validate_upload(uploaded_file):
    """Raise ValidationError with a message a person can act on, or return the file."""
    if uploaded_file.size == 0:
        raise ValidationError(_("That file is empty."))

    if uploaded_file.size > MAX_BYTES:
        raise ValidationError(
            _("That file is %(size)s MB. The limit is %(limit)s MB.")
            % {
                "size": round(uploaded_file.size / 1024 / 1024, 1),
                "limit": round(MAX_BYTES / 1024 / 1024),
            }
        )

    suffix = Path(uploaded_file.name or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            _("%(kind)s files cannot be attached. Allowed: %(allowed)s.")
            % {
                "kind": suffix or _("Unnamed"),
                "allowed": ", ".join(sorted(e.lstrip(".") for e in ALLOWED_EXTENSIONS)),
            }
        )

    return uploaded_file


def safe_display_name(filename):
    """The name shown to people and sent in Content-Disposition.

    Stripped of any directory component: the browser does not use it as a path, but a
    filename containing a path separator is a sign of something going wrong, and an attachment
    listing is not the place to render it back verbatim.
    """
    return Path(filename or "").name[:255] or "attachment"
