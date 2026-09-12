"""
The download view's security contract (FR-015, FR-023, FR-024).

An attachment is the easiest thing in a support system to get wrong, because a file URL looks
inert and behaves like anything else the server will hand out. Four separate failures are
possible and each is tested here:

1. Reading a file belonging to another department.
2. Reading a file attached to an internal note as a customer.
3. An uploaded .html or .svg executing in an agent's browser when served back.
4. Guessing another file's URL.
"""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.attachments.models import Attachment
from apps.customers.models import Note, Organization
from apps.tickets.models import Category, Message, Ticket


def _attach(
    message=None,
    note=None,
    *,
    department,
    branch,
    uploader,
    name="evidence.png",
    content=b"fake image bytes",
    content_type="image/png",
):
    return Attachment.objects.create(
        message=message,
        note=note,
        file=SimpleUploadedFile(name, content, content_type=content_type),
        original_filename=name,
        content_type=content_type,
        size_bytes=len(content),
        uploaded_by=uploader,
        department=department,
        branch=branch,
    )


@pytest.fixture
def public_attachment(ticket, agent, department, branch):
    message = Message.objects.create(
        ticket=ticket,
        author=agent,
        direction=Message.Direction.OUTBOUND,
        visibility=Message.Visibility.PUBLIC,
        channel=ticket.origin_channel,
        body="Here it is",
    )
    return _attach(message=message, department=department, branch=branch, uploader=agent)


@pytest.fixture
def internal_attachment(ticket, agent, department, branch):
    message = Message.objects.create(
        ticket=ticket,
        author=agent,
        direction=Message.Direction.OUTBOUND,
        visibility=Message.Visibility.INTERNAL,
        channel=ticket.origin_channel,
        body="Team only",
    )
    return _attach(
        message=message,
        department=department,
        branch=branch,
        uploader=agent,
        name="carrier-dispute.pdf",
        content_type="application/pdf",
    )


# --- 1. scope ---


@pytest.mark.django_db
def test_an_agent_can_download_an_attachment_in_their_scope(agent_client, public_attachment):
    response = agent_client.get(reverse("attachments:download", args=[public_attachment.pk]))
    assert response.status_code == 200


@pytest.mark.django_db
def test_an_out_of_scope_attachment_returns_404_not_403(
    agent_client, other_department, branch, contact, administrator
):
    """FR-024: a 403 confirms the file exists. Only a 404 discloses nothing."""
    category = Category.objects.create(name="Other", department=other_department)
    other_ticket = Ticket.objects.create(
        contact=contact,
        subject="Elsewhere",
        description="...",
        category=category,
        origin_channel=Ticket.Channel.WEB_FORM,
        department=other_department,
        branch=branch,
    )
    message = Message.objects.create(
        ticket=other_ticket,
        author=administrator,
        direction=Message.Direction.OUTBOUND,
        visibility=Message.Visibility.PUBLIC,
        channel=other_ticket.origin_channel,
        body="x",
    )
    hidden = _attach(
        message=message,
        department=other_department,
        branch=branch,
        uploader=administrator,
        name="secret-contract.pdf",
    )

    response = agent_client.get(reverse("attachments:download", args=[hidden.pk]))
    assert response.status_code == 404
    assert b"secret-contract" not in response.content


@pytest.mark.django_db
def test_an_anonymous_visitor_cannot_download_anything(client, public_attachment):
    response = client.get(reverse("attachments:download", args=[public_attachment.pk]))
    assert response.status_code == 302
    assert reverse("accounts:sign_in") in response.url


@pytest.mark.django_db
def test_a_guessed_id_does_not_leak_existence(agent_client):
    response = agent_client.get(reverse("attachments:download", args=[999999]))
    assert response.status_code == 404


# --- 2. internal visibility ---


@pytest.mark.django_db
def test_staff_can_download_an_internal_attachment(agent_client, internal_attachment):
    assert (
        agent_client.get(reverse("attachments:download", args=[internal_attachment.pk])).status_code
        == 200
    )


@pytest.mark.django_db
def test_an_attachment_on_an_internal_message_is_marked_internal(internal_attachment):
    assert internal_attachment.is_internal is True


@pytest.mark.django_db
def test_an_attachment_on_a_note_is_internal(agent, department, branch):
    """Notes are staff-only by definition, so anything hanging off one is too — otherwise the
    attachment is a way around FR-015 that the message-level filter never sees."""
    organization = Organization.objects.create(name="Najd", department=department, branch=branch)
    note = Note.objects.create(
        organization=organization,
        author=agent,
        body="Called them",
        department=department,
        branch=branch,
    )
    attachment = _attach(note=note, department=department, branch=branch, uploader=agent)
    assert attachment.is_internal is True


@pytest.mark.django_db
def test_a_public_attachment_is_not_internal(public_attachment):
    assert public_attachment.is_internal is False


# --- 3. serving an uploaded file back ---


@pytest.mark.django_db
def test_files_are_served_as_a_download_not_rendered(agent_client, public_attachment):
    """Content-Disposition: attachment is what stops an uploaded .html or .svg executing in
    the browser of the agent who opens it — a stored XSS straight into the staff interface."""
    response = agent_client.get(reverse("attachments:download", args=[public_attachment.pk]))

    disposition = response.headers["Content-Disposition"]
    assert disposition.startswith("attachment;")
    assert response.headers["X-Content-Type-Options"] == "nosniff"


@pytest.mark.django_db
def test_the_uploaded_content_type_is_never_echoed_back(
    ticket, agent, agent_client, department, branch
):
    """The stored content type is attacker-controlled. Serving it back is what turns an
    uploaded file into a rendered page."""
    message = Message.objects.create(
        ticket=ticket,
        author=agent,
        direction=Message.Direction.OUTBOUND,
        visibility=Message.Visibility.PUBLIC,
        channel=ticket.origin_channel,
        body="x",
    )
    hostile = _attach(
        message=message,
        department=department,
        branch=branch,
        uploader=agent,
        name="notes.txt",
        content=b"<script>alert(1)</script>",
        content_type="text/html",
    )

    response = agent_client.get(reverse("attachments:download", args=[hostile.pk]))

    assert response.headers["Content-Type"] != "text/html"
    assert "html" not in response.headers["Content-Type"].lower()


@pytest.mark.django_db
def test_the_download_name_carries_no_directory_component(
    ticket, agent, agent_client, department, branch
):
    message = Message.objects.create(
        ticket=ticket,
        author=agent,
        direction=Message.Direction.OUTBOUND,
        visibility=Message.Visibility.PUBLIC,
        channel=ticket.origin_channel,
        body="x",
    )
    traversal = _attach(
        message=message,
        department=department,
        branch=branch,
        uploader=agent,
        name="../../../etc/passwd",
    )

    response = agent_client.get(reverse("attachments:download", args=[traversal.pk]))
    disposition = response.headers["Content-Disposition"]

    assert "../" not in disposition
    assert "passwd" in disposition  # the name survives; the path does not


# --- 4. the stored path ---


@pytest.mark.django_db
def test_the_stored_path_is_generated_not_the_uploaded_name(ticket, agent, department, branch):
    message = Message.objects.create(
        ticket=ticket,
        author=agent,
        direction=Message.Direction.OUTBOUND,
        visibility=Message.Visibility.PUBLIC,
        channel=ticket.origin_channel,
        body="x",
    )
    attachment = _attach(
        message=message,
        department=department,
        branch=branch,
        uploader=agent,
        name="../../etc/passwd.png",
    )

    assert "etc/passwd" not in attachment.file.name
    assert ".." not in attachment.file.name
    assert attachment.file.name.startswith("attachments/")
    assert attachment.original_filename == "../../etc/passwd.png"  # kept for display only


@pytest.mark.django_db
def test_two_uploads_of_the_same_name_do_not_collide(ticket, agent, department, branch):
    message = Message.objects.create(
        ticket=ticket,
        author=agent,
        direction=Message.Direction.OUTBOUND,
        visibility=Message.Visibility.PUBLIC,
        channel=ticket.origin_channel,
        body="x",
    )
    first = _attach(message=message, department=department, branch=branch, uploader=agent)
    second = _attach(message=message, department=department, branch=branch, uploader=agent)
    assert first.file.name != second.file.name
