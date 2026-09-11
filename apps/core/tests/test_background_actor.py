"""
FR-027: a background task writing to a customer record must record the human who started it.

A Celery task has no HTTP request, so django-auditlog's request-based actor attribution does
not apply. Without an explicit actor the trail would attribute human-initiated work to
nobody, and "who sent this reply to the customer" becomes unanswerable — which is the exact
question the audit trail exists to answer.
"""

import pytest
from auditlog.models import LogEntry
from django.urls import reverse

from apps.tickets.models import Message


@pytest.mark.django_db
def test_task_attributes_its_write_with_no_request_in_scope(agent, ticket):
    """Called the way a real worker calls it: no HTTP request, no ambient actor context.

    Going through the view instead would prove nothing here — CELERY_TASK_ALWAYS_EAGER runs
    the task inside the request, where auditlog's request-scoped actor is still set, so the
    write is attributed by accident and the test passes over a production bug.
    """
    from apps.messaging.tasks import send_ticket_reply_email

    message = Message.objects.create(
        ticket=ticket,
        author=agent,
        direction=Message.Direction.OUTBOUND,
        visibility=Message.Visibility.PUBLIC,
        channel=ticket.origin_channel,
        body="We have opened an investigation.",
        delivery_status=Message.DeliveryStatus.PENDING,
    )
    LogEntry.objects.all().delete()  # ignore the create; the task's own write is the subject

    send_ticket_reply_email(message_id=message.pk, actor_id=agent.pk)

    message.refresh_from_db()
    assert message.delivery_status == Message.DeliveryStatus.SENT

    actors = {e.actor for e in LogEntry.objects.get_for_object(message)}
    assert agent in actors, (
        "The delivery-status write was not attributed to the agent who sent the reply. "
        f"Actors recorded: {actors}"
    )


@pytest.mark.django_db
def test_without_an_actor_the_write_is_recorded_as_unattributed(agent, ticket):
    """Shows what the previous test is actually protecting against: omit the actor and the
    trail cannot answer who replied."""
    from apps.messaging.tasks import send_ticket_reply_email

    message = Message.objects.create(
        ticket=ticket,
        author=agent,
        direction=Message.Direction.OUTBOUND,
        visibility=Message.Visibility.PUBLIC,
        channel=ticket.origin_channel,
        body="Anonymous send.",
        delivery_status=Message.DeliveryStatus.PENDING,
    )
    LogEntry.objects.all().delete()

    send_ticket_reply_email(message_id=message.pk)  # no actor_id

    actors = {e.actor for e in LogEntry.objects.get_for_object(message)}
    assert actors == {None}


@pytest.mark.django_db
def test_view_passes_the_actor_through_to_the_task(agent_client, agent, ticket):
    """The end-to-end path: the view must supply actor_id, or the task above gets None."""
    agent_client.post(
        reverse("tickets:reply", args=[ticket.reference]),
        {"body": "We have opened an investigation."},
    )
    message = Message.objects.get(ticket=ticket)
    assert message.delivery_status == Message.DeliveryStatus.SENT

    actors = {e.actor for e in LogEntry.objects.get_for_object(message)}
    assert agent in actors


@pytest.mark.django_db
def test_task_refuses_to_run_without_an_actor():
    """apps.core.tasks.ActorRequiredTask makes the omission fail loudly rather than
    silently recording a system user."""
    from apps.core.tasks import ActorRequiredTask

    task = ActorRequiredTask()
    task.run = lambda *a, **kw: None
    task.name = "test-task"

    with pytest.raises(ValueError, match="explicit actor"):
        task.run_as(None)
