"""
An attachment must not become a way around FR-015.

Phase 9 established that no internal *message* reaches a customer. An attachment is a second
route to the same failure and one the message-level filter cannot see: the file hangs off the
message rather than being part of its body, so a customer-facing output that correctly filters
messages can still list, link or send the file attached to one.
"""

import pytest
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.attachments.models import Attachment
from apps.tickets.models import Message
from apps.tickets.services.visibility import customer_facing_context, public_messages_for

SECRET_FILE = "carrier-dispute-internal.pdf"


@pytest.fixture
def ticket_with_attachments(ticket, agent, department, branch):
    public = Message.objects.create(
        ticket=ticket,
        author=agent,
        direction=Message.Direction.OUTBOUND,
        visibility=Message.Visibility.PUBLIC,
        channel=ticket.origin_channel,
        body="Here is the delivery note you asked for.",
    )
    internal = Message.objects.create(
        ticket=ticket,
        author=agent,
        direction=Message.Direction.OUTBOUND,
        visibility=Message.Visibility.INTERNAL,
        channel=ticket.origin_channel,
        body="Carrier signature does not match.",
    )
    for message, name in ((public, "delivery-note.pdf"), (internal, SECRET_FILE)):
        Attachment.objects.create(
            message=message,
            file=SimpleUploadedFile(name, b"bytes", content_type="application/pdf"),
            original_filename=name,
            content_type="application/pdf",
            size_bytes=5,
            uploaded_by=agent,
            department=department,
            branch=branch,
        )
    return ticket


@pytest.mark.django_db
def test_the_customer_facing_context_reaches_no_internal_attachment(ticket_with_attachments):
    """The context exposes public messages; walking their attachments must never arrive at a
    file on an internal one."""
    context = customer_facing_context(ticket_with_attachments)

    reachable = [
        attachment.original_filename
        for message in context["public_messages"]
        for attachment in message.attachments.all()
    ]
    assert "delivery-note.pdf" in reachable
    assert SECRET_FILE not in reachable


@pytest.mark.django_db
def test_the_public_filter_excludes_the_internal_attachments_parent(ticket_with_attachments):
    public = list(public_messages_for(ticket_with_attachments))
    assert all(m.visibility == Message.Visibility.PUBLIC for m in public)
    assert not any(a.original_filename == SECRET_FILE for m in public for a in m.attachments.all())


@pytest.mark.django_db
def test_an_outbound_email_names_no_internal_attachment(agent_client, ticket_with_attachments):
    mail.outbox.clear()
    agent_client.post(
        reverse("tickets:reply", args=[ticket_with_attachments.reference]),
        {"body": "Update as promised."},
    )

    assert len(mail.outbox) == 1
    sent = mail.outbox[0]
    assert SECRET_FILE not in sent.body
    assert SECRET_FILE not in sent.subject
    for content, _mime in getattr(sent, "alternatives", []):
        assert SECRET_FILE not in content


@pytest.mark.django_db
def test_the_public_confirmation_page_names_no_attachment_at_all(client, ticket_with_attachments):
    body = client.get(
        reverse("intake:submitted", args=[ticket_with_attachments.reference])
    ).content.decode()
    assert SECRET_FILE not in body
    assert "delivery-note.pdf" not in body


@pytest.mark.django_db
def test_uploading_to_an_internal_note_marks_the_file_internal(agent_client, ticket, agent):
    agent_client.post(
        reverse("tickets:note", args=[ticket.reference]),
        {
            "body": "Team only.",
            "attachments": SimpleUploadedFile("evidence.png", b"img", content_type="image/png"),
        },
    )

    attachment = Attachment.objects.get()
    assert attachment.is_internal is True
    assert attachment.message.visibility == Message.Visibility.INTERNAL


@pytest.mark.django_db
def test_uploading_to_a_reply_marks_the_file_public(agent_client, ticket, agent):
    agent_client.post(
        reverse("tickets:reply", args=[ticket.reference]),
        {
            "body": "Attached.",
            "attachments": SimpleUploadedFile("shot.png", b"img", content_type="image/png"),
        },
    )

    attachment = Attachment.objects.get()
    assert attachment.is_internal is False


@pytest.mark.django_db
def test_a_refused_file_does_not_discard_the_message(agent_client, ticket):
    """One bad file must not lose the reply the agent just wrote."""
    agent_client.post(
        reverse("tickets:reply", args=[ticket.reference]),
        {
            "body": "The reply text.",
            "attachments": SimpleUploadedFile(
                "payload.html", b"<script>", content_type="text/html"
            ),
        },
    )

    assert Message.objects.filter(body="The reply text.").exists()
    assert not Attachment.objects.exists()
