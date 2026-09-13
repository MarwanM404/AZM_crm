"""
The administrator can see that the work landed (T010, FR-003).

The reported defect was an account that did not appear. Once it appears, there is still a gap
worth closing: an administrator who has just added someone to a list of twenty has no way to
confirm it except by reading twenty rows and remembering which were there before.

Confirmation is cheap and it is what turns "the list looks the same" from a worry into a fact.
"""

import pytest
from django.urls import reverse

from apps.accounts.models import User

pytestmark = pytest.mark.django_db


def add(client, administrator, name="New Colleague", email="new.colleague@example.com"):
    return client.post(
        reverse("administration:user_new"),
        {
            "full_name": name,
            "email": email,
            "role": User.Role.AGENT,
            "department": administrator.department_id,
            "branch": administrator.branch_id,
        },
        follow=True,
    )


def test_the_new_account_is_confirmed_by_name(admin_client_, administrator):
    response = add(admin_client_, administrator)

    body = response.content.decode()
    assert "New Colleague" in body
    assert "new.colleague@example.com" in body


def test_the_confirmation_distinguishes_it_from_the_accounts_already_there(
    admin_client_, administrator, agent, supervisor
):
    """Being present in a list of four is not confirmation. The row has to be marked."""
    response = add(admin_client_, administrator)

    body = response.content.decode()
    marker_position = body.find("row--created")
    assert marker_position != -1, "the newly created account is not distinguished in any way"

    # And the mark is on the right row: the created account's name follows it more closely
    # than any other account's does.
    new_at = body.find("New Colleague", marker_position)
    agent_at = body.find(agent.full_name, marker_position)
    assert new_at != -1
    assert agent_at == -1 or new_at < agent_at


def test_the_mark_does_not_persist_into_a_later_visit(admin_client_, administrator):
    """A permanent "new" badge stops meaning new. It marks this visit, not this account."""
    add(admin_client_, administrator)

    body = admin_client_.get(reverse("administration:users")).content.decode()

    assert "row--created" not in body


def test_an_ordinary_visit_marks_nothing(admin_client_, administrator, agent):
    body = admin_client_.get(reverse("administration:users")).content.decode()

    assert "row--created" not in body
