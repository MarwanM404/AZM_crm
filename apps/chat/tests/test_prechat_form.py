"""
Starting a conversation (T037, T040).

Contact matching is the request form's, not a second implementation — chat must not become
another way to create customers, or the same person ends up as two contacts depending on how
they got in touch.
"""

import pytest
from django.urls import reverse

from apps.chat.models import Conversation
from apps.chat.services import presence
from apps.customers.models import Contact
from apps.tickets.models import Ticket

pytestmark = pytest.mark.django_db


@pytest.fixture
def online_agent(agent):
    presence.go_online(agent.pk, capacity=3)
    return agent


def _payload(category, **overrides):
    data = {
        "full_name": "Sara Ahmed",
        "email": "sara@najd-trading.example",
        "subject": "My order never arrived",
        "category": category.pk,
    }
    data.update(overrides)
    return data


def test_chat_is_not_offered_when_nobody_is_online(client, category, branch):
    """FR-039. A queue behind nobody is a waiting room with no door."""
    response = client.get(reverse("chat:availability"))
    assert response.json()["available"] is False


def test_chat_is_offered_when_an_agent_is_online(client, online_agent, branch):
    assert client.get(reverse("chat:availability")).json()["available"] is True


def test_starting_creates_a_conversation_and_a_ticket(client, online_agent, category, branch):
    response = client.post(reverse("chat:start"), _payload(category))
    body = response.json()

    assert response.status_code == 200
    assert body["available"] is True
    assert body["token"]

    conversation = Conversation.objects.get()
    assert conversation.ticket.origin_channel == Ticket.Channel.CHAT
    assert conversation.contact.full_name == "Sara Ahmed"


def test_no_ticket_reference_is_given_at_the_start(client, online_agent, category, branch):
    """FR-040: the agent may attach the conversation to an existing ticket later, and a
    reference handed out now could be one the customer can no longer use."""
    body = client.post(reverse("chat:start"), _payload(category)).json()

    assert "reference" not in body
    assert not any("AZM-" in str(value) for value in body.values())


def test_the_stored_token_is_a_hash_not_the_token(client, online_agent, category, branch):
    token = client.post(reverse("chat:start"), _payload(category)).json()["token"]
    conversation = Conversation.objects.get()

    assert conversation.visitor_token_hash != token
    assert token not in conversation.visitor_token_hash


def test_a_known_email_reuses_the_existing_contact(client, online_agent, category, branch, contact):
    """The same person must not become two contacts depending on how they got in touch."""
    before = Contact.objects.count()
    client.post(
        reverse("chat:start"),
        _payload(category, email="sara@najd-trading.example", full_name="Sara A."),
    )
    assert Contact.objects.count() == before


def test_an_unknown_email_creates_a_contact_with_no_organization(
    client, online_agent, category, branch
):
    """MVP FR-040: chat cannot determine an employer any better than the request form can."""
    client.post(reverse("chat:start"), _payload(category, email="stranger@elsewhere.example"))
    created = Contact.objects.get(details__value="stranger@elsewhere.example")
    assert created.organization is None


def test_an_available_agent_is_assigned(client, online_agent, category, branch):
    body = client.post(reverse("chat:start"), _payload(category)).json()
    assert body["assigned"] is True

    conversation = Conversation.objects.get()
    assert conversation.assigned_to_id == online_agent.pk
    assert conversation.state == Conversation.State.ACTIVE


def test_a_busy_desk_queues_the_visitor(client, online_agent, category, branch):
    presence.claim_slot(online_agent.pk)
    presence.claim_slot(online_agent.pk)
    presence.claim_slot(online_agent.pk)  # capacity 3, all taken

    body = client.post(reverse("chat:start"), _payload(category)).json()

    assert body["assigned"] is False
    assert body["position"] == 1
    assert Conversation.objects.get().state == Conversation.State.WAITING


def test_a_closed_desk_offers_the_request_form_with_what_was_typed(client, category, branch):
    """FR-018: anything already typed is carried over rather than lost."""
    body = client.post(reverse("chat:start"), _payload(category)).json()

    assert body["available"] is False
    assert body["fallback"] == "/request/"
    assert body["carry"]["subject"] == "My order never arrived"
    assert not Conversation.objects.exists()


def test_an_incomplete_form_is_rejected(client, online_agent, category, branch):
    response = client.post(reverse("chat:start"), _payload(category, email=""))
    assert response.status_code == 422
    assert "email" in response.json()["errors"]


def test_the_visitor_needs_no_account(client, online_agent, category, branch):
    """FR-005. These endpoints are reachable signed out, by design."""
    for route in ("chat:availability", "chat:widget"):
        assert client.get(reverse(route)).status_code == 200
