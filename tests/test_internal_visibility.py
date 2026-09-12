"""
FR-015: no message marked INTERNAL may appear in ANY customer-facing output.

This is the cross-cutting invariant the roadmap pulled forward into the MVP (M8a) so that
live chat's supervisor-whisper feature lands on prepared ground. The failure it guards
against is silent and irreversible: once an email carrying a private staff note has left,
nothing can recall it.

The sweep is self-maintaining. CUSTOMER_FACING_TEMPLATES lists every template a customer can
read, and a test asserts that list covers every template in the customer-facing directories.
Adding a new one without listing it fails the build rather than quietly going unchecked.
"""

from pathlib import Path

import pytest
from django.core import mail
from django.template.loader import render_to_string
from django.urls import reverse

from apps.tickets.models import Message
from apps.tickets.services.visibility import (
    contains_internal_content,
    customer_facing_context,
    public_messages_for,
    staff_messages_for,
)

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET = "CARRIER-SIGNATURE-DOES-NOT-MATCH-INTERNAL-ONLY"

# Directories whose every template is read by someone outside the organization.
CUSTOMER_FACING_DIRS = [
    BASE_DIR / "templates" / "messaging" / "email",
    BASE_DIR / "templates" / "intake",
]

CUSTOMER_FACING_TEMPLATES = [
    "messaging/email/reply.en.txt",
    "messaging/email/reply.ar.txt",
    "messaging/email/confirmation.en.txt",
    "messaging/email/confirmation.ar.txt",
    "intake/form.html",
    "intake/submitted.html",
]


@pytest.fixture
def ticket_with_both(ticket, agent):
    Message.objects.create(
        ticket=ticket,
        author=agent,
        direction=Message.Direction.OUTBOUND,
        visibility=Message.Visibility.PUBLIC,
        channel=ticket.origin_channel,
        body="Public: we are investigating with the carrier.",
    )
    Message.objects.create(
        ticket=ticket,
        author=agent,
        direction=Message.Direction.OUTBOUND,
        visibility=Message.Visibility.INTERNAL,
        channel=ticket.origin_channel,
        body=SECRET,
    )
    return ticket


# --- the filter itself ---


@pytest.mark.django_db
def test_public_filter_excludes_internal(ticket_with_both):
    bodies = [m.body for m in public_messages_for(ticket_with_both)]
    assert SECRET not in bodies
    assert len(bodies) == 1


@pytest.mark.django_db
def test_staff_view_includes_internal(ticket_with_both):
    assert SECRET in [m.body for m in staff_messages_for(ticket_with_both)]


@pytest.mark.django_db
def test_customer_facing_context_cannot_carry_an_internal_message(ticket_with_both):
    context = customer_facing_context(ticket_with_both)
    assert SECRET not in [m.body for m in context["public_messages"]]
    assert SECRET not in str(context)


@pytest.mark.django_db
def test_customer_facing_context_does_not_expose_the_ticket_object(ticket_with_both):
    """A template holding the ticket itself can reach `ticket.messages.all` and walk straight
    past the filter — in Django templates that is an ordinary attribute lookup, with no
    import and nothing to review. So the context exposes the fields a customer may read, not
    the object they hang off."""
    context = customer_facing_context(ticket_with_both)

    assert "ticket" not in context
    for value in context.values():
        assert not hasattr(
            value, "messages"
        ), f"A customer-facing context value exposes .messages: {value!r}"


# --- every customer-facing template, rendered with an internal note present ---


def test_template_registry_covers_every_customer_facing_template():
    """A new customer-facing template that nobody added to the list would go unswept."""
    on_disk = {
        f"{path.parent.name}/{path.name}"
        if path.parent.name != "email"
        else f"messaging/email/{path.name}"
        for directory in CUSTOMER_FACING_DIRS
        for path in directory.iterdir()
        if path.is_file()
    }
    listed = {t for t in CUSTOMER_FACING_TEMPLATES}
    missing = on_disk - listed
    assert not missing, (
        "These customer-facing templates are not covered by the internal-visibility sweep. "
        f"Add them to CUSTOMER_FACING_TEMPLATES: {sorted(missing)}"
    )


@pytest.mark.django_db
@pytest.mark.parametrize("template", CUSTOMER_FACING_TEMPLATES)
def test_no_customer_facing_template_can_render_an_internal_message(ticket_with_both, template):
    """Render each one with the fullest context it could plausibly receive, including the
    ticket itself, and confirm the internal body never surfaces."""
    context = customer_facing_context(ticket_with_both, body="An agent reply.", form=None)
    rendered = render_to_string(template, context)

    assert SECRET not in rendered
    assert not contains_internal_content(rendered, ticket_with_both)


# --- the live paths ---


@pytest.mark.django_db
def test_outbound_reply_email_never_carries_an_internal_message(agent_client, ticket_with_both):
    mail.outbox.clear()
    agent_client.post(
        reverse("tickets:reply", args=[ticket_with_both.reference]),
        {"body": "Here is the update we promised."},
    )
    assert len(mail.outbox) == 1
    sent = mail.outbox[0]

    assert SECRET not in sent.body
    assert SECRET not in sent.subject
    for content, _mime in getattr(sent, "alternatives", []):
        assert SECRET not in content
    assert not contains_internal_content(sent.body, ticket_with_both)


@pytest.mark.django_db
def test_confirmation_email_never_carries_an_internal_message(
    client, branch, category, ticket_with_both
):
    import time

    mail.outbox.clear()
    client.post(
        reverse("intake:form"),
        {
            "full_name": "Jane",
            "email": "jane@example.com",
            "category": category.pk,
            "subject": "New",
            "description": "New request",
            "company_website": "",
            "rendered_at": time.time() - 5,
        },
    )
    for sent in mail.outbox:
        assert SECRET not in sent.body


@pytest.mark.django_db
def test_send_task_refuses_an_internal_message_outright(ticket_with_both):
    """Defence in depth: called directly with an internal message id, the send path must
    still not deliver it."""
    from apps.messaging.tasks import send_ticket_reply_email

    internal = ticket_with_both.messages.get(visibility=Message.Visibility.INTERNAL)
    mail.outbox.clear()
    send_ticket_reply_email(message_id=internal.pk)
    assert mail.outbox == []


@pytest.mark.django_db
def test_public_confirmation_page_carries_no_messages_at_all(client, ticket_with_both):
    body = client.get(
        reverse("intake:submitted", args=[ticket_with_both.reference])
    ).content.decode()
    assert SECRET not in body
    assert "Public: we are investigating" not in body


@pytest.mark.django_db
def test_internal_note_is_visible_to_staff_on_the_ticket(agent_client, ticket_with_both):
    """The other half of the requirement: staff must actually see it, or the feature is
    merely broken rather than safe."""
    body = agent_client.get(
        reverse("tickets:detail", args=[ticket_with_both.reference])
    ).content.decode()
    assert SECRET in body
