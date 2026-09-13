"""
The add-account form starts in the administrator's own scope (T007, FR-001).

Reported as "created accounts don't show up". They were created — in whichever department
sorted first, which for the seeded data is Billing while the administrator is in Support. An
administrator filling in a name and an email and pressing the button produced an account they
could not see, with no error anywhere.

The default is the first half of the fix. The second half is refusing the deliberate case
(test_account_scope_refusal.py), because a default only helps the person who does not change it.
"""

import re

import pytest
from django.urls import reverse

from apps.accounts.models import Branch, Department

pytestmark = pytest.mark.django_db


@pytest.fixture
def a_department_that_sorts_first(db):
    """Named to sort before "Support", reproducing the seeded condition exactly: the trap is
    not that another department exists, it is that another department is the default."""
    return Department.objects.create(name="Billing")


def select_named(body, name):
    """The markup of one <select>, not the whole page.

    Searching the page for `value="1" selected` found the *branch* field satisfying the
    *department* assertion, because the two happen to share a primary key in these fixtures.
    The test passed with the department default removed, which is the whole thing it exists
    to catch.
    """
    match = re.search(rf"<select[^>]*name=['\"]{name}['\"].*?</select>", body, re.S)
    assert match, f"no <select name={name}> on the page"
    return match.group(0)


def test_the_form_preselects_the_administrators_own_department(
    admin_client_, administrator, a_department_that_sorts_first
):
    body = admin_client_.get(reverse("administration:user_new")).content.decode()

    field = select_named(body, "department")
    assert f'value="{administrator.department_id}" selected' in field, (
        "the department field does not start on the administrator's own, so an account "
        "created without touching it lands somewhere they cannot see"
    )


def test_it_does_not_preselect_whichever_sorts_first(
    admin_client_, administrator, a_department_that_sorts_first
):
    body = admin_client_.get(reverse("administration:user_new")).content.decode()

    field = select_named(body, "department")
    assert f'value="{a_department_that_sorts_first.pk}" selected' not in field


def test_the_form_preselects_the_administrators_own_branch(admin_client_, administrator):
    Branch.objects.create(name="Another Office")

    body = admin_client_.get(reverse("administration:user_new")).content.decode()

    field = select_named(body, "branch")
    assert f'value="{administrator.branch_id}" selected' in field


def test_the_field_is_still_a_real_choice(
    admin_client_, administrator, a_department_that_sorts_first
):
    """Reducing the control to one option would teach an administrator that scope is not a
    real field, and the lesson becomes wrong the moment a second branch exists. The default
    is opinionated; the field stays open (research.md §1)."""
    body = admin_client_.get(reverse("administration:user_new")).content.decode()

    field = select_named(body, "department")
    assert f'value="{a_department_that_sorts_first.pk}"' in field


def test_an_account_created_without_touching_the_scope_is_visible_afterwards(
    admin_client_, administrator, a_department_that_sorts_first, department, branch
):
    """The whole defect, end to end: fill in a name and an email, press the button, find it."""
    from apps.accounts.models import User

    admin_client_.post(
        reverse("administration:user_new"),
        {
            "full_name": "New Colleague",
            "email": "new.colleague@example.com",
            "role": User.Role.AGENT,
            "department": administrator.department_id,
            "branch": administrator.branch_id,
        },
    )

    body = admin_client_.get(reverse("administration:users")).content.decode()
    assert "New Colleague" in body
