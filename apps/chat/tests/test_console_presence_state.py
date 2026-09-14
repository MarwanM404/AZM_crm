"""
The console agrees with the server about whether you are online (reported 2026-09-14).

Reported as "the go online button doesn't work". It does — the socket connects, presence is
recorded, and `/chat/availability/` starts answering yes. What fails is the next page load:
the component hardcodes `online: false`, so the status reads "Offline" again and the agent
concludes the button did nothing.

The page was half right, which is what made it convincing. The view computes `online` and the
template uses it for the pill's colour, so the pill renders green *and says Offline* — two
parts of one control disagreeing, because only one of them was given the answer.
"""

import re

import pytest
from django.urls import reverse

from apps.chat.services import presence
from apps.chat.services.redis_client import reset_for_tests

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clean():
    reset_for_tests()
    yield
    reset_for_tests()


def component_arguments(body):
    """What the page hands to `chatConsole(...)`."""
    match = re.search(r"chatConsole\(([^)]*)\)", body)
    assert match, "the console page does not initialise the component at all"
    return [a.strip() for a in match.group(1).split(",")]


def test_an_online_agent_is_told_they_are_online(agent_client, agent):
    presence.go_online(agent.pk, capacity=3)

    body = agent_client.get(reverse("chat:console")).content.decode()

    assert "true" in component_arguments(body), (
        "the console starts as offline however the agent actually is, so going online appears "
        "to do nothing the moment the page is reloaded"
    )


def test_an_offline_agent_is_told_they_are_offline(agent_client, agent):
    body = agent_client.get(reverse("chat:console")).content.decode()

    assert "false" in component_arguments(body)


def test_the_two_halves_of_the_pill_agree(agent_client, agent):
    """The pill takes its colour from the server and its text from the component. They were
    given different answers, so it rendered green and said Offline."""
    presence.go_online(agent.pk, capacity=3)

    body = agent_client.get(reverse("chat:console")).content.decode()
    pill = re.search(r'<span class="pill[^"]*"[^>]*x-text="statusLabel"', body)

    assert pill, "the status pill is no longer rendered as expected"
    assert "pill--open" in pill.group(0)
    assert "true" in component_arguments(body)


def test_going_offline_is_reflected_too(agent_client, agent):
    presence.go_online(agent.pk, capacity=3)
    presence.go_offline(agent.pk)

    body = agent_client.get(reverse("chat:console")).content.decode()

    assert "false" in component_arguments(body)


def test_a_lapsed_heartbeat_reads_as_offline(agent_client, agent):
    """Presence expires on its own (presence.py). The console must follow it rather than
    remember a state that is no longer true."""
    from apps.chat.services.redis_client import get_client

    presence.go_online(agent.pk, capacity=3)
    get_client().force_expire(f"chat:presence:{agent.pk}")

    body = agent_client.get(reverse("chat:console")).content.decode()

    assert "false" in component_arguments(body)
