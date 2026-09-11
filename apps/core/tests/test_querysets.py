import pytest

from apps.customers.models import Organization


@pytest.mark.django_db
def test_for_user_excludes_rows_outside_department_and_branch(
    agent, department, other_department, branch
):
    own = Organization.objects.create(name="In scope", department=department, branch=branch)
    other = Organization.objects.create(
        name="Out of scope", department=other_department, branch=branch
    )

    visible = Organization.objects.for_user(agent)

    assert own in visible
    assert other not in visible
