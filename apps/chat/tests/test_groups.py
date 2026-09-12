"""
Group naming (T011, T025) — the security boundary of this feature.

A whisper is published to the staff group. The customer's socket never joins it. That is what
makes FR-025 a property of the wiring rather than of remembering to filter: a leak would
require actively adding the customer to the staff group, not merely forgetting a branch.

Which means these names are not a formatting detail. If two modules computed them slightly
differently — a trailing separator, a string id versus an integer — the customer's socket and
the whisper would end up in groups that look the same to a reader and are different to Redis,
or worse, the same when they should differ. One module, tested.
"""

import pytest

from apps.chat.services import groups


def test_public_and_staff_groups_are_different():
    assert groups.public_group(1) != groups.staff_group(1)


def test_each_conversation_gets_its_own_groups():
    assert groups.public_group(1) != groups.public_group(2)
    assert groups.staff_group(1) != groups.staff_group(2)


@pytest.mark.parametrize("given", [7, "7"])
def test_an_id_given_as_a_string_or_an_integer_names_the_same_group(given):
    """A conversation id arrives from a URL as a string and from the ORM as an integer. If
    those produced different group names, an agent and a visitor could join groups that read
    identically in the code and differ in Redis."""
    assert groups.public_group(given) == groups.public_group(7)
    assert groups.staff_group(given) == groups.staff_group(7)


def test_no_conversation_id_can_collide_with_another_conversations_group():
    """Names are built from the id alone, so a crafted id must not produce another's group."""
    names = {groups.public_group(i) for i in range(1, 200)}
    names |= {groups.staff_group(i) for i in range(1, 200)}
    assert len(names) == 398


def test_group_names_are_valid_for_the_channel_layer():
    """Channels rejects group names over 100 characters or containing anything outside
    [A-Za-z0-9_.-]. A name rejected at runtime fails inside a consumer, far from here."""
    import re

    for name in (groups.public_group(999999), groups.staff_group(999999)):
        assert len(name) < 100
        assert re.fullmatch(r"[A-Za-z0-9_.\-]+", name), name


def test_the_module_exposes_no_way_to_get_the_staff_group_for_a_visitor():
    """A visitor consumer that could ask for 'the groups for this conversation' would
    eventually be handed both. The module offers two named functions and no such helper."""
    public_api = {n for n in dir(groups) if not n.startswith("_")}
    assert "public_group" in public_api
    assert "staff_group" in public_api
    assert not any(
        n in public_api for n in ("all_groups", "groups_for", "both_groups", "groups")
    ), (
        "A helper returning every group for a conversation is one autocomplete away from a "
        "visitor socket joining the staff group."
    )
