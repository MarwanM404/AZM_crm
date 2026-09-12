"""Upload validation. The public form takes files from the open internet, so these run on
every path rather than only the staff ones."""

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import translation

from apps.attachments.services.validation import (
    MAX_BYTES,
    safe_display_name,
    validate_upload,
)


def _file(name, size=1024, content_type="application/pdf"):
    return SimpleUploadedFile(name, b"x" * size, content_type=content_type)


def test_an_ordinary_document_is_accepted():
    assert validate_upload(_file("invoice.pdf")) is not None


@pytest.mark.parametrize(
    "name", ["shot.png", "photo.JPG", "sheet.xlsx", "notes.txt", "archive.zip", "report.docx"]
)
def test_the_kinds_a_support_desk_actually_receives_are_accepted(name):
    assert validate_upload(_file(name)) is not None


@pytest.mark.parametrize("name", ["payload.html", "logo.svg", "page.htm", "data.xml"])
def test_renderable_types_are_refused(name):
    """These are absent from the allowlist on purpose. An SVG is an image to a person and a
    script host to a browser; the download view refuses to render anything, but keeping them
    out is the cheaper of the two defences."""
    with pytest.raises(ValidationError):
        validate_upload(_file(name))


@pytest.mark.parametrize("name", ["run.exe", "script.sh", "lib.so", "macro.docm"])
def test_executable_types_are_refused(name):
    with pytest.raises(ValidationError):
        validate_upload(_file(name))


def test_a_file_with_no_extension_is_refused():
    with pytest.raises(ValidationError):
        validate_upload(_file("README"))


def test_an_empty_file_is_refused():
    """Almost always a failed upload rather than an intentional one; storing it just confuses
    the agent who opens it.

    The language is pinned because the assertion reads the message: the default account
    language is Arabic, so a test asserting English wording must say so.
    """
    with translation.override("en"), pytest.raises(ValidationError, match="empty"):
        validate_upload(SimpleUploadedFile("empty.pdf", b"", content_type="application/pdf"))


def test_an_oversized_file_is_refused_with_both_numbers():
    with translation.override("en"), pytest.raises(ValidationError) as caught:
        validate_upload(_file("huge.pdf", size=MAX_BYTES + 1))

    message = "; ".join(caught.value.messages)
    assert "MB" in message  # says how big it was and what the limit is, not just "too large"


def test_the_extension_check_is_case_insensitive():
    assert validate_upload(_file("SCAN.PDF")) is not None


def test_a_double_extension_is_judged_on_the_last_one():
    """`invoice.pdf.exe` is an executable, whatever it is pretending to be."""
    with pytest.raises(ValidationError):
        validate_upload(_file("invoice.pdf.exe"))


@pytest.mark.parametrize(
    "given,expected",
    [
        ("../../../etc/passwd", "passwd"),
        ("/absolute/path/report.pdf", "report.pdf"),
        ("plain.png", "plain.png"),
        ("", "attachment"),
    ],
)
def test_display_names_carry_no_directory_component(given, expected):
    assert safe_display_name(given) == expected


def test_an_arabic_filename_survives():
    assert safe_display_name("صورة-الشحنة.png") == "صورة-الشحنة.png"
