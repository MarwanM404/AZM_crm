"""
A queue behind nobody is a waiting room with no door (T104, FR-039).

When no agent is online, chat is not offered *at all* — not offered-and-then-queued, not
offered with an apology. The visitor sees the request form, which is a thing that actually
works when nobody is there: it creates a ticket someone answers later.

The distinction FR-039 draws is between "online" and "free". Agents online and all busy is a
queue. No agents at all is a closed desk.
"""

import pytest
from django.urls import reverse

from apps.chat.models import Conversation
from apps.chat.services import presence
from apps.chat.services.redis_client import reset_for_tests

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clean():
    reset_for_tests()
    yield
    reset_for_tests()


def test_the_widget_does_not_offer_chat(client, agent, department, branch):
    body = client.get(reverse("chat:widget")).content.decode()

    assert "chat-prechat" not in body


def test_the_widget_points_at_the_request_form_instead(client, agent, department, branch):
    body = client.get(reverse("chat:widget")).content.decode()

    assert reverse("intake:form") in body


def test_the_widget_does_offer_chat_when_someone_is_online(client, agent, department, branch):
    presence.go_online(agent.pk, capacity=3)

    body = client.get(reverse("chat:widget")).content.decode()

    assert "chat-prechat" in body


def test_starting_a_chat_is_refused_and_redirected(client, agent, category, department, branch):
    body = client.post(
        reverse("chat:start"),
        {
            "full_name": "Sara",
            "email": "sara@example.com",
            "subject": "Where is my order",
            "category": category.pk,
        },
    ).json()

    assert body["available"] is False
    assert body["fallback"] == reverse("intake:form")


def test_what_they_typed_is_carried_into_the_form(client, agent, category, department, branch):
    """Retyping your question because a desk was closed is the moment a customer with a
    question becomes a customer with a complaint."""
    body = client.post(
        reverse("chat:start"),
        {
            "full_name": "Sara",
            "email": "sara@example.com",
            "subject": "Where is my order",
            "category": category.pk,
        },
    ).json()

    assert body["carry"]["full_name"] == "Sara"
    assert body["carry"]["email"] == "sara@example.com"
    assert body["carry"]["subject"] == "Where is my order"


def test_no_conversation_is_created(client, agent, category, department, branch):
    """A conversation nobody will ever join is a ticket with no subject and an empty
    transcript, cluttering the queue an agent works from."""
    client.post(
        reverse("chat:start"),
        {
            "full_name": "Sara",
            "email": "sara@example.com",
            "subject": "Where is my order",
            "category": category.pk,
        },
    )

    assert Conversation.objects.count() == 0
