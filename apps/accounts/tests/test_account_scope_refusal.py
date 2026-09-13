"""
An account that would be invisible is not created (T008, T009, T011, FR-002, FR-006, FR-020).

The default fixes the administrator who does not touch the field. This fixes the one who does —
and it refuses rather than quietly correcting, which is the more interesting decision.

Silently moving the account into the administrator's own scope would also make it visible, and
would be a second invisible outcome: they asked for Billing, got Support, and were told nothing.
That is the same defect wearing different clothes, which is why FR-020 exists as a requirement
of its own rather than as a note on this one.
"""

import pytest
from django.urls import reverse

from apps.accounts.models import User

pytestmark = pytest.mark.django_db


def create(client, administrator, **overrides):
    payload = {
        "full_name": "Somebody Else",
        "email": "somebody.else@example.com",
        "role": User.Role.AGENT,
        "department": administrator.department_id,
        "branch": administrator.branch_id,
    }
    payload.update(overrides)
    return client.post(reverse("administration:user_new"), payload)


def test_a_department_the_administrator_does_not_administer_is_refused(
    admin_client_, administrator, other_department
):
    response = create(admin_client_, administrator, department=other_department.pk)

    assert response.status_code == 422


@pytest.mark.parametrize(
    "language,phrase",
    [("en", "would not be visible"), ("ar", "ظاهرًا لك")],
)
def test_the_refusal_says_the_account_would_not_be_visible(
    admin_client_, administrator, other_department, language, phrase
):
    """ "Invalid department" tells an administrator nothing they can act on. The message names
    the consequence, because the consequence is the reason for the rule.

    Checked in both languages: an explanation that only exists in English is not an
    explanation for half this desk, and the first version of this test asserted English
    wording and passed only because the string had not been translated yet.
    """
    administrator.language = language
    administrator.save(update_fields=["language"])

    response = create(admin_client_, administrator, department=other_department.pk)

    assert phrase in response.content.decode()


def test_nothing_is_created(admin_client_, administrator, other_department):
    create(admin_client_, administrator, department=other_department.pk)

    assert not User.objects.filter(email="somebody.else@example.com").exists()


def test_it_is_not_silently_corrected_into_the_administrators_own_scope(
    admin_client_, administrator, other_department
):
    """FR-020. An administrator who chose another department meant something by it, and being
    given a different result without being told is the defect this feature exists to remove."""
    create(admin_client_, administrator, department=other_department.pk)

    created = User.objects.filter(email="somebody.else@example.com").first()
    assert created is None, (
        "the account was created in the administrator's own department instead of being "
        "refused — a second silent outcome in place of the first"
    )


def test_a_branch_the_administrator_does_not_administer_is_refused(admin_client_, administrator):
    from apps.accounts.models import Branch

    elsewhere = Branch.objects.create(name="Another Office")

    response = create(admin_client_, administrator, branch=elsewhere.pk)

    assert response.status_code == 422
    assert not User.objects.filter(email="somebody.else@example.com").exists()


def test_an_account_with_no_department_is_refused(admin_client_, administrator):
    """FR-006. The state a scopeless account starts in must not be reachable from here."""
    response = create(admin_client_, administrator, department="")

    assert response.status_code == 422
    assert not User.objects.filter(email="somebody.else@example.com").exists()


def test_an_account_with_no_branch_is_refused(admin_client_, administrator):
    response = create(admin_client_, administrator, branch="")

    assert response.status_code == 422
    assert not User.objects.filter(email="somebody.else@example.com").exists()


def test_the_administrators_own_scope_is_accepted(admin_client_, administrator):
    """The refusals above must not be passing because creation is broken for everyone."""
    response = create(admin_client_, administrator)

    assert response.status_code in (302, 200)
    assert User.objects.filter(email="somebody.else@example.com").exists()


def test_moving_an_existing_account_out_of_scope_is_still_allowed(
    admin_client_, administrator, other_department, agent
):
    """The rule above applies to creation and NOT to moving, and the difference is real.

    Moving a colleague to another department is the operation succeeding — losing sight of
    them is what the administrator asked for. Creating one there is an accident. An earlier
    version of this work refused both, which broke `test_scope_assignment.py` and would have
    removed a working MVP feature (FR-025) in the name of fixing a different one.

    It remains an action whose result the administrator cannot see afterwards, which FR-020
    says should be stated at the time. That is a confirmation step, and it is not this story.
    """
    response = admin_client_.post(
        reverse("administration:user_scope", args=[agent.pk]),
        {"department": other_department.pk, "branch": administrator.branch_id},
    )
    agent.refresh_from_db()

    assert response.status_code in (302, 200)
    assert agent.department_id == other_department.pk
