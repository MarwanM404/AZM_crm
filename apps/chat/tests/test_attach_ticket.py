"""
Attaching a conversation to an existing ticket (T068, T073).

A customer starting a chat does not know they already have an open ticket about the same
problem. The agent does. Attaching re-points the transcript onto that ticket so the history
stays in one place, and retires the placeholder the conversation was started with.

Two properties matter more than the mechanics:

* The placeholder is **soft-deleted, never destroyed** — its reference may already have been
  quoted somewhere, and FR-020 makes deletion recoverable regardless.
* Both tickets are **audited**. A ticket that grows a transcript and a ticket that disappears
  are the same event seen from two sides; recording only one leaves it unreconstructable.
"""

import pytest
from auditlog.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from apps.chat.services import messaging
from apps.chat.services.redis_client import reset_for_tests
from apps.tickets.models import Ticket

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clean():
    reset_for_tests()
    yield
    reset_for_tests()


@pytest.fixture
def existing_ticket(db, department, branch, category, contact):
    """The ticket the customer already had open before they opened the chat."""
    return Ticket.objects.create(
        contact=contact,
        subject="Order #4471 never arrived",
        description="Raised by email last week.",
        category=category,
        origin_channel=Ticket.Channel.EMAIL,
        department=department,
        branch=branch,
    )


@pytest.fixture
def other_conversation(db, department, branch, category, contact):
    """A second, independent conversation. `assigned_conversation` is built *from* the
    `conversation` fixture — they are one row — so a test about two conversations needs this.
    """
    from apps.chat.models import Conversation

    ticket = Ticket.objects.create(
        contact=contact,
        subject="A second chat",
        description="",
        category=category,
        origin_channel=Ticket.Channel.CHAT,
        department=department,
        branch=branch,
    )
    return Conversation.objects.create(
        ticket=ticket,
        contact=contact,
        visitor_token_hash="second",
        department=department,
        branch=branch,
    )


def _attach(client, conversation, ticket):
    return client.post(reverse("chat:attach", args=[conversation.pk]), {"ticket": ticket.pk})


def audit_entries_for(obj):
    return LogEntry.objects.filter(
        content_type=ContentType.objects.get_for_model(obj), object_pk=str(obj.pk)
    )


def test_the_transcript_moves_to_the_chosen_ticket(
    agent_client, assigned_conversation, existing_ticket
):
    messaging.visitor_message(assigned_conversation, "Still nothing today")
    messaging.agent_message(
        assigned_conversation, assigned_conversation.assigned_to, "Checking the courier"
    )
    placeholder = assigned_conversation.ticket

    response = _attach(agent_client, assigned_conversation, existing_ticket)

    assert response.status_code in (200, 204, 302)
    assert list(existing_ticket.messages.order_by("created_at").values_list("body", flat=True)) == [
        "Still nothing today",
        "Checking the courier",
    ]
    assert placeholder.messages.count() == 0


def test_the_conversation_now_points_at_the_chosen_ticket(
    agent_client, assigned_conversation, existing_ticket
):
    _attach(agent_client, assigned_conversation, existing_ticket)
    assigned_conversation.refresh_from_db()

    assert assigned_conversation.ticket_id == existing_ticket.pk


def test_messages_sent_after_attaching_land_on_the_chosen_ticket(
    agent_client, assigned_conversation, existing_ticket
):
    """The re-point has to survive the rest of the conversation, not just the moment of the
    move — otherwise the second half of the transcript lands on a deleted ticket."""
    _attach(agent_client, assigned_conversation, existing_ticket)
    assigned_conversation.refresh_from_db()

    messaging.visitor_message(assigned_conversation, "Said after attaching")

    assert existing_ticket.messages.filter(body="Said after attaching").exists()


def test_the_placeholder_is_soft_deleted_not_destroyed(
    agent_client, assigned_conversation, existing_ticket, agent
):
    placeholder = assigned_conversation.ticket

    _attach(agent_client, assigned_conversation, existing_ticket)

    assert not Ticket.objects.filter(pk=placeholder.pk).exists()
    recovered = Ticket.all_objects.get(pk=placeholder.pk)
    assert recovered.is_deleted
    assert recovered.deleted_by_id == agent.pk


def test_both_tickets_are_audited(agent_client, assigned_conversation, existing_ticket):
    placeholder = assigned_conversation.ticket
    before_placeholder = audit_entries_for(placeholder).count()
    before_target = audit_entries_for(existing_ticket).count()

    _attach(agent_client, assigned_conversation, existing_ticket)

    assert audit_entries_for(placeholder).count() > before_placeholder
    assert audit_entries_for(existing_ticket).count() > before_target


def test_a_ticket_outside_the_agents_scope_is_refused_as_absent(
    agent_client, assigned_conversation, other_department_ticket
):
    """FR-024: 404, not 403. A 403 would confirm that this reference exists in another
    department — which is the fact being protected."""
    response = _attach(agent_client, assigned_conversation, other_department_ticket)

    assert response.status_code == 404
    assigned_conversation.refresh_from_db()
    assert assigned_conversation.ticket_id != other_department_ticket.pk
    assert other_department_ticket.messages.count() == 0


def test_a_conversation_outside_the_agents_scope_is_refused_as_absent(
    agent_client, conversation, other_department, branch, category, contact, existing_ticket
):
    conversation.department = other_department
    conversation.save(update_fields=["department"])

    response = _attach(agent_client, conversation, existing_ticket)

    assert response.status_code == 404


def test_an_ineligible_target_is_refused_and_nothing_moves(
    agent_client, assigned_conversation, existing_ticket, monkeypatch
):
    """The endpoint must consult the eligibility rule rather than encoding it inline — the
    rule is policy and will change; the move is mechanism and will not."""
    from apps.chat.services import transcript

    monkeypatch.setattr(transcript, "can_attach_to", lambda conversation, ticket: False)
    messaging.visitor_message(assigned_conversation, "Should not move")
    placeholder = assigned_conversation.ticket

    response = _attach(agent_client, assigned_conversation, existing_ticket)

    assert response.status_code == 422
    assigned_conversation.refresh_from_db()
    assert assigned_conversation.ticket_id == placeholder.pk
    assert existing_ticket.messages.count() == 0
    assert Ticket.objects.filter(pk=placeholder.pk).exists()


def test_attaching_to_the_ticket_it_already_has_is_a_no_op(agent_client, assigned_conversation):
    """A double-clicked button must not soft-delete the ticket it just attached to."""
    own_ticket = assigned_conversation.ticket
    messaging.visitor_message(assigned_conversation, "Keep me")

    _attach(agent_client, assigned_conversation, own_ticket)

    assigned_conversation.refresh_from_db()
    assert assigned_conversation.ticket_id == own_ticket.pk
    assert Ticket.objects.filter(pk=own_ticket.pk).exists()
    assert own_ticket.messages.filter(body="Keep me").exists()


# --- eligibility (transcript.can_attach_to) ---
#
# The rule is the strict one: same contact, not settled, not another live conversation's
# ticket. Attaching is not reversible through the UI, so a wrong refusal costs the agent a
# second attempt while a wrong acceptance corrupts a customer's history permanently.


def test_a_ticket_belonging_to_a_different_customer_is_refused(
    agent_client, assigned_conversation, department, branch, category
):
    """Merging one customer's words into another's history is not recoverable by apology."""
    from apps.customers.models import Contact

    someone_else = Contact.objects.create(
        full_name="Other Person", department=department, branch=branch
    )
    their_ticket = Ticket.objects.create(
        contact=someone_else,
        subject="Unrelated",
        description="",
        category=category,
        origin_channel=Ticket.Channel.EMAIL,
        department=department,
        branch=branch,
    )
    messaging.visitor_message(assigned_conversation, "Private to me")

    response = _attach(agent_client, assigned_conversation, their_ticket)

    assert response.status_code == 422
    assert their_ticket.messages.count() == 0


@pytest.mark.parametrize("settled", [Ticket.Status.RESOLVED, Ticket.Status.CLOSED])
def test_a_settled_ticket_is_refused(agent_client, assigned_conversation, existing_ticket, settled):
    """Reopening is a deliberate act with its own audit entry. A transcript arriving quietly
    on a resolved ticket makes the resolution timestamp already on it untrue."""
    existing_ticket.status = settled
    existing_ticket.save(update_fields=["status"])

    response = _attach(agent_client, assigned_conversation, existing_ticket)

    assert response.status_code == 422
    assert existing_ticket.messages.count() == 0


def test_a_ticket_held_by_another_live_conversation_is_refused(
    agent_client, assigned_conversation, other_conversation, existing_ticket
):
    """Two live transcripts interleaved by timestamp in one ticket, with nothing marking
    where one ends and the other begins."""
    other_conversation.ticket = existing_ticket
    other_conversation.save(update_fields=["ticket"])

    response = _attach(agent_client, assigned_conversation, existing_ticket)

    assert response.status_code == 422


def test_a_ticket_whose_conversation_has_ended_may_still_receive_one(
    agent_client, assigned_conversation, other_conversation, existing_ticket
):
    """The objection is to two *live* transcripts. A returning customer continuing yesterday's
    chat on the same ticket is exactly what attaching is for."""
    from apps.chat.models import Conversation

    other_conversation.ticket = existing_ticket
    other_conversation.state = Conversation.State.ENDED
    other_conversation.save(update_fields=["ticket", "state"])
    messaging.visitor_message(assigned_conversation, "Back again about this")

    response = _attach(agent_client, assigned_conversation, existing_ticket)

    assert response.status_code in (200, 204, 302)
    assert existing_ticket.messages.filter(body="Back again about this").exists()


def test_the_console_offers_attach_only_where_it_would_work(
    agent_client, assigned_conversation, existing_ticket, department, branch, category, contact
):
    """A button that answers 422 teaches agents to distrust the button."""
    settled = Ticket.objects.create(
        contact=contact,
        subject="Already sorted",
        description="",
        category=category,
        origin_channel=Ticket.Channel.EMAIL,
        status=Ticket.Status.RESOLVED,
        department=department,
        branch=branch,
    )

    body = agent_client.get(
        reverse("chat:conversation", args=[assigned_conversation.pk])
    ).content.decode()

    assert f'value="{existing_ticket.pk}"' in body
    assert f'value="{settled.pk}"' not in body
