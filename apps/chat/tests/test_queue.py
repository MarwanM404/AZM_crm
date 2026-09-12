"""The waiting queue (T013, T027). Longest waiting first (FR-017), scoped like everything."""

import pytest

from apps.chat.services import queue
from apps.chat.services.redis_client import reset_for_tests


@pytest.fixture(autouse=True)
def clean():
    reset_for_tests()
    yield
    reset_for_tests()


@pytest.mark.django_db
def test_a_waiting_visitor_has_a_position(department, branch):
    queue.join("token-a", department.pk, branch.pk)
    assert queue.position("token-a", department.pk, branch.pk) == 1


@pytest.mark.django_db
def test_positions_reflect_arrival_order(department, branch):
    for token in ("first", "second", "third"):
        queue.join(token, department.pk, branch.pk)

    assert queue.position("first", department.pk, branch.pk) == 1
    assert queue.position("third", department.pk, branch.pk) == 3


@pytest.mark.django_db
def test_the_longest_waiting_visitor_is_taken_first(department, branch):
    """FR-017. The whole reason this is a sorted set rather than a list."""
    for token in ("first", "second"):
        queue.join(token, department.pk, branch.pk)

    assert queue.take_next(department.pk, branch.pk) == "first"
    assert queue.take_next(department.pk, branch.pk) == "second"
    assert queue.take_next(department.pk, branch.pk) is None


@pytest.mark.django_db
def test_leaving_removes_a_visitor(department, branch):
    """FR-019: no agent should be handed a conversation nobody is waiting on."""
    queue.join("going", department.pk, branch.pk)
    queue.leave("going", department.pk, branch.pk)

    assert queue.position("going", department.pk, branch.pk) is None
    assert queue.take_next(department.pk, branch.pk) is None


@pytest.mark.django_db
def test_positions_move_up_when_someone_ahead_is_taken(department, branch):
    for token in ("first", "second"):
        queue.join(token, department.pk, branch.pk)
    queue.take_next(department.pk, branch.pk)

    assert queue.position("second", department.pk, branch.pk) == 1


@pytest.mark.django_db
def test_queues_are_scoped_by_department_and_branch(department, other_department, branch):
    """A queue that ignored scope would route a visitor to an agent who cannot see their
    tickets — the same rule as every other list in this product."""
    queue.join("theirs", other_department.pk, branch.pk)

    assert queue.take_next(department.pk, branch.pk) is None
    assert queue.waiting_count(department.pk, branch.pk) == 0
    assert queue.waiting_count(other_department.pk, branch.pk) == 1


@pytest.mark.django_db
def test_joining_twice_does_not_create_two_places(department, branch):
    """A visitor with two browser tabs is one person waiting, not two (spec edge case)."""
    queue.join("same-token", department.pk, branch.pk)
    queue.join("same-token", department.pk, branch.pk)
    assert queue.waiting_count(department.pk, branch.pk) == 1


@pytest.mark.django_db
def test_draining_returns_everyone_waiting(department, branch):
    """FR-042: when the last agent goes offline, everyone waiting is moved to the request
    form rather than left queued for a desk that has closed."""
    for token in ("a", "b", "c"):
        queue.join(token, department.pk, branch.pk)

    drained = queue.drain(department.pk, branch.pk)

    assert drained == ["a", "b", "c"]
    assert queue.waiting_count(department.pk, branch.pk) == 0
