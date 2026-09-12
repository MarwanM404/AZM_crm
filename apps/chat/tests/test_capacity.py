"""
Capacity (T051, FR-012).

An agent handling three conversations well is the point of chat; a fourth arriving because
nothing stopped it is how all four get handled badly.
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


def _start(client, category):
    return client.post(
        reverse("chat:start"),
        {
            "full_name": "Visitor",
            "email": f"v{id(client)}@example.com",
            "subject": "Help",
            "category": category.pk,
        },
    ).json()


def test_an_agent_receives_up_to_their_capacity(client, agent, category, branch):
    presence.go_online(agent.pk, capacity=3)

    from django.test import Client

    for index in range(3):
        visitor = Client()
        body = visitor.post(
            reverse("chat:start"),
            {
                "full_name": f"Visitor {index}",
                "email": f"v{index}@example.com",
                "subject": "Help",
                "category": category.pk,
            },
        ).json()
        assert body["assigned"] is True

    assert Conversation.objects.filter(state=Conversation.State.ACTIVE).count() == 3
    assert presence.capacity_remaining(agent.pk) == 0


def test_the_fourth_visitor_queues_rather_than_overloading_the_agent(
    client, agent, category, branch
):
    presence.go_online(agent.pk, capacity=3)
    from django.test import Client

    for index in range(3):
        Client().post(
            reverse("chat:start"),
            {
                "full_name": f"Visitor {index}",
                "email": f"v{index}@example.com",
                "subject": "Help",
                "category": category.pk,
            },
        )

    fourth = (
        Client()
        .post(
            reverse("chat:start"),
            {
                "full_name": "Fourth",
                "email": "fourth@example.com",
                "subject": "Help",
                "category": category.pk,
            },
        )
        .json()
    )

    assert fourth["assigned"] is False
    assert fourth["position"] == 1
    assert Conversation.objects.filter(state=Conversation.State.WAITING).count() == 1


def test_ending_a_conversation_frees_capacity_for_the_next(client, agent, category, branch):
    presence.go_online(agent.pk, capacity=1)
    from django.test import Client

    Client().post(
        reverse("chat:start"),
        {
            "full_name": "First",
            "email": "first@example.com",
            "subject": "Help",
            "category": category.pk,
        },
    )
    assert presence.capacity_remaining(agent.pk) == 0

    from apps.chat.services import lifecycle

    conversation = Conversation.objects.get()
    lifecycle.end(conversation, reason=Conversation.EndReason.ENDED_BY_AGENT, ended_by=agent)

    assert presence.capacity_remaining(agent.pk) == 1


def test_capacity_is_per_agent_not_shared(client, agent, other_agent, category, branch):
    presence.go_online(agent.pk, capacity=1)
    presence.go_online(other_agent.pk, capacity=1)
    from django.test import Client

    for index in range(2):
        body = (
            Client()
            .post(
                reverse("chat:start"),
                {
                    "full_name": f"V{index}",
                    "email": f"v{index}@example.com",
                    "subject": "Help",
                    "category": category.pk,
                },
            )
            .json()
        )
        assert body["assigned"] is True

    assert Conversation.objects.filter(state=Conversation.State.ACTIVE).count() == 2
