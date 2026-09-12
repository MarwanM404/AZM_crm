"""
Agent presence (T012, T026).

Presence is stored in Redis with a TTL rather than in a table, and the reasoning is the
inverse of the usual one: presence is *supposed* to be ephemeral. An agent whose browser
closed, whose laptop slept, or whose server restarted is not online — and a database row
saying "online" goes on saying it, because the process that would have corrected it is the one
that died. No heartbeat, no key, not online: the failure mode corrects itself.

These run against a fake Redis so the behaviour is tested without the service.
"""

import pytest

from apps.chat.services import presence


@pytest.fixture(autouse=True)
def clean_presence():
    presence.reset_for_tests()
    yield
    presence.reset_for_tests()


@pytest.mark.django_db
def test_an_agent_is_offline_until_they_go_online(agent):
    assert presence.is_online(agent.pk) is False


@pytest.mark.django_db
def test_going_online_makes_an_agent_available(agent):
    presence.go_online(agent.pk, capacity=3)
    assert presence.is_online(agent.pk) is True
    assert presence.capacity_remaining(agent.pk) == 3


@pytest.mark.django_db
def test_an_agent_disappears_when_their_key_expires(agent):
    """The whole point of the TTL: nothing has to notice a crash for it to be corrected."""
    presence.go_online(agent.pk, capacity=3)
    presence.expire_now_for_tests(agent.pk)
    assert presence.is_online(agent.pk) is False


@pytest.mark.django_db
def test_a_heartbeat_keeps_an_agent_online(agent):
    presence.go_online(agent.pk, capacity=3)
    presence.heartbeat(agent.pk)
    assert presence.is_online(agent.pk) is True


@pytest.mark.django_db
def test_a_heartbeat_from_an_offline_agent_does_not_bring_them_back(agent):
    """An agent who went offline deliberately must stay offline; only going online does that.
    Otherwise a stale browser tab would silently re-enlist someone who had finished."""
    presence.go_online(agent.pk, capacity=3)
    presence.go_offline(agent.pk)
    presence.heartbeat(agent.pk)
    assert presence.is_online(agent.pk) is False


@pytest.mark.django_db
def test_taking_a_conversation_consumes_capacity(agent):
    presence.go_online(agent.pk, capacity=2)
    presence.claim_slot(agent.pk)
    assert presence.capacity_remaining(agent.pk) == 1
    presence.claim_slot(agent.pk)
    assert presence.capacity_remaining(agent.pk) == 0
    assert presence.has_capacity(agent.pk) is False


@pytest.mark.django_db
def test_releasing_a_conversation_frees_capacity(agent):
    presence.go_online(agent.pk, capacity=1)
    presence.claim_slot(agent.pk)
    presence.release_slot(agent.pk)
    assert presence.has_capacity(agent.pk) is True


@pytest.mark.django_db
def test_capacity_never_goes_negative(agent):
    """Releasing more than was claimed is a bug elsewhere, but it must not make an agent
    appear to have infinite room."""
    presence.go_online(agent.pk, capacity=1)
    presence.release_slot(agent.pk)
    presence.release_slot(agent.pk)
    assert presence.capacity_remaining(agent.pk) == 1


@pytest.mark.django_db
def test_online_agents_lists_only_those_with_room(agent, other_agent, department, branch):
    presence.go_online(agent.pk, capacity=1)
    presence.go_online(other_agent.pk, capacity=1)
    presence.claim_slot(other_agent.pk)

    available = presence.agents_with_capacity([agent.pk, other_agent.pk])
    assert agent.pk in available
    assert other_agent.pk not in available


@pytest.mark.django_db
def test_anyone_online_is_false_when_the_desk_is_empty(agent):
    """FR-039 hangs off this: with nobody online, chat is not offered at all."""
    assert presence.anyone_online([agent.pk]) is False
    presence.go_online(agent.pk, capacity=3)
    assert presence.anyone_online([agent.pk]) is True
