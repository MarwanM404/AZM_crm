"""
FR-015: no message marked INTERNAL may appear in ANY customer-facing output.

This is the cross-cutting invariant the roadmap pulled forward into the MVP (M8a) so that
live chat's supervisor-whisper feature lands on prepared ground. It now covers that feature:
the customer's chat window and the fragments broadcast to the public group are swept here
alongside the email and intake templates. The failure it guards
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

TEMPLATE_ROOT = BASE_DIR / "templates"

# Directories whose every template is read by someone outside the organization.
CUSTOMER_FACING_DIRS = [
    TEMPLATE_ROOT / "messaging" / "email",
    TEMPLATE_ROOT / "intake",
    # The customer portal (spec 004, FR-014). The whole directory is customer-facing by
    # definition — a customer is the only person who signs into it — so it is swept by
    # directory. Nothing here is listed by hand: a portal template that nobody remembered is
    # exactly the failure this feature was told to prevent.
    TEMPLATE_ROOT / "portal",
]


def templates_in(directory):
    """Every template under a customer-facing directory, named as Django loads it.

    Recursive on purpose. `iterdir` was used here first and stopped at the top level, which
    would have left templates/portal/email/ — the confirmation and reset messages, the most
    unrecallable output this product produces — outside the sweep while the directory above
    them reported covered.
    """
    return sorted(
        str(path.relative_to(TEMPLATE_ROOT)) for path in directory.rglob("*") if path.is_file()
    )


# Live chat is the exception to the directory rule: templates/chat/ holds both the customer's
# window and the agent's console, so it cannot be swept wholesale. Every chat template is
# classified below instead, and a test asserts the two lists together cover the directory —
# so a new one has to be consciously placed on one side or the other.
CHAT_CUSTOMER_FACING = [
    "chat/widget.html",
    "chat/partials/message.html",
    "chat/partials/system.html",
]

CHAT_STAFF_ONLY = [
    "chat/console.html",
    "chat/conversation.html",
    "chat/supervise.html",
    "chat/partials/whisper.html",
    "chat/partials/conversation_list.html",
]

CUSTOMER_FACING_TEMPLATES = [
    "messaging/email/reply.en.txt",
    "messaging/email/reply.ar.txt",
    "messaging/email/confirmation.en.txt",
    "messaging/email/confirmation.ar.txt",
    "intake/form.html",
    "intake/submitted.html",
    *CHAT_CUSTOMER_FACING,
    # Discovered rather than listed. The lists above are maintained by hand because their
    # directories hold staff-facing files too; templates/portal/ holds nothing else, so the
    # sweep picks up a new screen the moment it exists.
    *templates_in(TEMPLATE_ROOT / "portal"),
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
    on_disk = {name for directory in CUSTOMER_FACING_DIRS for name in templates_in(directory)}
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


# --- live chat (FR-025) ---


def test_every_chat_template_is_classified():
    """templates/chat/ holds both sides of the boundary, so it cannot be swept by directory.
    A new template that nobody classified would otherwise be neither swept nor noticed."""
    chat_dir = BASE_DIR / "templates" / "chat"
    on_disk = {
        str(path.relative_to(BASE_DIR / "templates"))
        for path in chat_dir.rglob("*.html")
        if path.is_file()
    }
    classified = set(CHAT_CUSTOMER_FACING) | set(CHAT_STAFF_ONLY)
    unclassified = on_disk - classified

    assert not unclassified, (
        "These chat templates are on neither side of the visibility boundary. Add each to "
        "CHAT_CUSTOMER_FACING (and it will be swept) or CHAT_STAFF_ONLY: "
        f"{sorted(unclassified)}"
    )


@pytest.mark.django_db
def test_the_customer_chat_window_cannot_render_an_internal_message(ticket_with_both):
    """The whisper partial is never reached from the customer's side, but the guarantee must
    not rest on the template being called correctly — render the customer's window with a
    conversation whose ticket carries an internal note and confirm it cannot surface."""
    from apps.tickets.services.visibility import public_messages_for

    rendered = render_to_string(
        "chat/widget.html",
        {
            "messages_": public_messages_for(ticket_with_both),
            "conversation": None,
            "form": None,
        },
    )

    assert SECRET not in rendered


@pytest.mark.django_db(transaction=True)
def test_an_internal_message_is_never_broadcast_to_the_public_group(conversation, supervisor):
    """Where the guarantee actually lives.

    chat/partials/message.html is naive on purpose — it renders whatever message it is given,
    and it is broadcast to the public group verbatim. Nothing in the template prevents an
    internal body appearing there; what prevents it is that internal messages are routed to
    whisper.html and the staff group by apps/chat/services/messaging.py, and never reach this
    fragment at all. So the assertion belongs on the routing, not on the template.
    """
    from apps.chat.services import groups, messaging

    sent = []

    def record(group_name, payload):
        sent.append((group_name, payload))

    original = messaging._broadcast
    messaging._broadcast = record
    try:
        messaging.whisper(conversation, supervisor, SECRET)
    finally:
        messaging._broadcast = original

    public = groups.public_group(conversation.pk)
    assert sent, "the whisper was not broadcast at all"
    for group_name, payload in sent:
        assert group_name != public, "a whisper was published to the customer's group"
        assert SECRET in payload["html"]  # it did reach staff, unmangled
    assert {group_name for group_name, _ in sent} == {groups.staff_group(conversation.pk)}
