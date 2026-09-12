"""
The agent console (T054, T055, T059).

One screen holding several conversations. Scoped like every other list in this product, and
showing the customer's context beside each conversation — an agent switching between three
chats cannot hold three customers' histories in their head.
"""

import pytest
from django.urls import reverse

from apps.chat.models import Conversation
from apps.chat.services import presence, unread
from apps.chat.services.redis_client import reset_for_tests

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clean():
    reset_for_tests()
    yield
    reset_for_tests()


def test_the_console_needs_a_signed_in_agent(client):
    response = client.get(reverse("chat:console"))
    assert response.status_code == 302
    assert reverse("accounts:sign_in") in response.url


def test_the_console_lists_the_agents_conversations(agent_client, assigned_conversation):
    body = agent_client.get(reverse("chat:console")).content.decode()
    assert assigned_conversation.contact.full_name in body


def test_the_console_shows_customer_context(agent_client, assigned_conversation):
    """An agent moving between three conversations cannot hold three customers' histories in
    their head, so each one carries its own."""
    body = agent_client.get(reverse("chat:console")).content.decode()

    assert assigned_conversation.contact.full_name in body
    assert assigned_conversation.ticket.reference in body


def test_another_agents_conversation_is_absent(agent_client, assigned_conversation, other_agent):
    assigned_conversation.assigned_to = other_agent
    assigned_conversation.save(update_fields=["assigned_to"])

    body = agent_client.get(reverse("chat:console")).content.decode()
    assert assigned_conversation.ticket.reference not in body


def test_a_conversation_in_another_department_is_not_found(
    agent_client, other_department_agent, other_department, branch, category, contact
):
    """MVP FR-024 applies here as everywhere: not forbidden, not found."""
    from apps.tickets.models import Category, Ticket

    other_category = Category.objects.create(name="Other", department=other_department)
    ticket = Ticket.objects.create(
        contact=contact,
        subject="Elsewhere",
        description="",
        category=other_category,
        origin_channel=Ticket.Channel.CHAT,
        department=other_department,
        branch=branch,
    )
    hidden = Conversation.objects.create(
        ticket=ticket,
        contact=contact,
        visitor_token_hash="q" * 64,
        assigned_to=other_department_agent,
        state=Conversation.State.ACTIVE,
        department=other_department,
        branch=branch,
    )

    response = agent_client.get(reverse("chat:conversation", args=[hidden.pk]))
    assert response.status_code == 404
    assert "Elsewhere" not in response.content.decode()


def test_the_console_shows_unread_counts(agent_client, agent, assigned_conversation):
    unread.mark(agent.pk, assigned_conversation.pk)
    unread.mark(agent.pk, assigned_conversation.pk)

    body = agent_client.get(reverse("chat:console")).content.decode()
    assert "2" in body


def test_the_console_reports_whether_the_agent_is_online(agent_client, agent):
    body = agent_client.get(reverse("chat:console")).content.decode()
    assert "chat-presence" in body

    presence.go_online(agent.pk, capacity=3)
    body = agent_client.get(reverse("chat:console")).content.decode()
    assert "chat-presence" in body


def test_opening_a_conversation_clears_its_unread(agent_client, agent, assigned_conversation):
    unread.mark(agent.pk, assigned_conversation.pk)
    agent_client.get(reverse("chat:conversation", args=[assigned_conversation.pk]))
    assert unread.count(agent.pk, assigned_conversation.pk) == 0


def test_a_supervisor_can_use_the_console(supervisor_client, assigned_conversation):
    """A Supervisor works tickets like an Agent (FR-037), chat included."""
    assert supervisor_client.get(reverse("chat:console")).status_code == 200
