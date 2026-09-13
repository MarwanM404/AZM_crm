"""
Periodic chat housekeeping.

FR-042 says nobody is left queued for a desk that has closed. The obvious trigger — an agent
pressing "go offline" — turns out to be the *rare* path, and reasoning about why is what this
task exists for.

When an agent ends a conversation, the longest-waiting visitor is connected to them
immediately, so an agent almost never reaches "holding nothing" while people are still
waiting. And FR-014 refuses to let them go offline while they hold anything. So the graceful
path mostly cannot strand anyone.

What actually strands people is the ungraceful one: the laptop that slept, the browser that
was closed, the machine that lost its network on the way home. Nothing fires an event for
those — the presence key simply stops being refreshed and expires (see presence.py). No event
means no handler, which means a sweep, which means this.
"""

from celery import shared_task


@shared_task
def close_deserted_desks() -> int:
    """Offer the request form to anyone waiting where no agent is online any more (FR-042).

    Returns the number of visitors moved, so the schedule can be observed rather than assumed.
    """
    from apps.accounts.models import Branch, Department
    from apps.chat.services import lifecycle, queue

    moved = 0
    for department_id in Department.objects.filter(is_active=True).values_list("pk", flat=True):
        for branch_id in Branch.objects.filter(is_active=True).values_list("pk", flat=True):
            if queue.waiting_count(department_id, branch_id) == 0:
                continue
            moved += len(lifecycle.desk_closed_if_empty(department_id, branch_id))
    return moved
