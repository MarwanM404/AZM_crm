"""
Agent queue, ticket detail, and the actions on a ticket.

Every view reads through `for_user()` or `get_object_or_404_for_user()`, so an out-of-scope
ticket returns 404 rather than 403 (FR-024 — a 403 would confirm the record exists).
htmx requests get the fragment they asked for; a full request gets the whole page.
"""

import logging

from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.accounts.permissions import require_administrator
from apps.core.shortcuts import get_object_or_404_for_user
from apps.messaging.tasks import send_ticket_reply_email
from apps.tickets.models import Category, Message, Ticket
from apps.tickets.services.lifecycle import InvalidTransition, apply_transition
from apps.tickets.services.visibility import staff_messages_for

logger = logging.getLogger(__name__)

PAGE_SIZE = 25


def _queue_queryset(request):
    """FR-038: every ticket in the agent's own department and branch, not only their own."""
    tickets = Ticket.objects.for_user(request.user).select_related(
        "contact", "organization", "category", "assigned_to"
    )

    if request.GET.get("assigned") == "me":
        tickets = tickets.filter(assigned_to=request.user)
    if status := request.GET.get("status"):
        tickets = tickets.filter(status=status)
    if priority := request.GET.get("priority"):
        tickets = tickets.filter(priority=priority)
    if category := request.GET.get("category"):
        tickets = tickets.filter(category_id=category)
    if query := request.GET.get("q", "").strip():
        from django.db.models import Q

        tickets = tickets.filter(
            Q(reference__icontains=query)
            | Q(subject__icontains=query)
            | Q(contact__full_name__icontains=query)
        )

    # Most urgent first, then oldest: the ticket that has waited longest at the highest
    # priority is the one an agent should pick up next.
    priority_order = {
        p: i
        for i, p in enumerate(
            [
                Ticket.Priority.URGENT,
                Ticket.Priority.HIGH,
                Ticket.Priority.NORMAL,
                Ticket.Priority.LOW,
            ]
        )
    }
    from django.db.models import Case, IntegerField, Value, When

    return tickets.annotate(
        priority_rank=Case(
            *[When(priority=p, then=Value(i)) for p, i in priority_order.items()],
            default=Value(99),
            output_field=IntegerField(),
        )
    ).order_by("priority_rank", "created_at")


def queue(request):
    tickets = _queue_queryset(request)[:PAGE_SIZE]
    context = {
        "section": "queue",
        "tickets": tickets,
        "statuses": Ticket.Status.choices,
        "priorities": Ticket.Priority.choices,
        "categories": Category.objects.filter(department=request.user.department, is_active=True),
        "filters": request.GET,
        "total": _queue_queryset(request).count(),
    }
    if request.htmx:
        return render(request, "tickets/partials/queue_list.html", context)
    return render(request, "tickets/queue.html", context)


def detail(request, reference):
    ticket = get_object_or_404_for_user(Ticket, request.user, reference=reference)
    return render(request, "tickets/detail.html", _detail_context(request, ticket))


def _detail_context(request, ticket):
    return {
        "ticket": ticket,
        "messages_": staff_messages_for(ticket).select_related("author"),
        "statuses": Ticket.Status.choices,
        "priorities": Ticket.Priority.choices,
        "categories": Category.objects.filter(department=ticket.department, is_active=True),
        "agents": User.objects.filter(
            department=ticket.department, branch=ticket.branch, is_active=True
        ),
        "allowed_statuses": sorted(ticket.ALLOWED_TRANSITIONS.get(ticket.status, set())),
    }


def _thread_response(request, ticket):
    """Every action returns the updated ticket pane, which is what htmx swaps in."""
    return render(request, "tickets/partials/ticket_pane.html", _detail_context(request, ticket))


@require_POST
def take(request, reference):
    """FR-008, FR-039: exactly one agent wins a contested unassigned ticket.

    The row is locked and re-read inside the transaction, so two simultaneous takes cannot
    both see assigned_to as null — the loser gets 409, not a silent overwrite.
    """
    ticket = get_object_or_404_for_user(Ticket, request.user, reference=reference)
    with transaction.atomic():
        locked = Ticket.objects.select_for_update().get(pk=ticket.pk)
        if locked.assigned_to_id is not None:
            if locked.assigned_to_id == request.user.pk:
                return _thread_response(request, locked)
            return HttpResponse(_("This ticket is already assigned to another agent."), status=409)
        locked.assigned_to = request.user
        locked.save(update_fields=["assigned_to"])
    return _thread_response(request, locked)


@require_POST
def assign(request, reference):
    """FR-008: reassignment away from another agent is an administrator action."""
    require_administrator(request)
    ticket = get_object_or_404_for_user(Ticket, request.user, reference=reference)
    try:
        agent = User.objects.get(
            pk=request.POST.get("agent"),
            department=ticket.department,
            branch=ticket.branch,
            is_active=True,
        )
    except (User.DoesNotExist, ValueError):
        return HttpResponse(_("Unknown agent."), status=422)

    ticket.assigned_to = agent
    ticket.save(update_fields=["assigned_to"])
    return _thread_response(request, ticket)


@require_POST
def status(request, reference):
    ticket = get_object_or_404_for_user(Ticket, request.user, reference=reference)
    try:
        apply_transition(ticket, request.POST.get("status"), actor=request.user)
    except InvalidTransition as exc:
        return HttpResponse(
            _("A ticket cannot move from %(current)s to %(requested)s.")
            % {"current": exc.current, "requested": exc.requested},
            status=422,
        )
    return _thread_response(request, ticket)


@require_POST
def fields(request, reference):
    """FR-010: category and priority changes take effect immediately and are audited."""
    ticket = get_object_or_404_for_user(Ticket, request.user, reference=reference)
    changed = []

    if (priority := request.POST.get("priority")) and priority in Ticket.Priority.values:
        ticket.priority = priority
        changed.append("priority")
    if category_id := request.POST.get("category"):
        try:
            ticket.category = Category.objects.get(pk=category_id, department=ticket.department)
            changed.append("category")
        except (Category.DoesNotExist, ValueError):
            return HttpResponse(_("Unknown category."), status=422)

    if changed:
        ticket.save(update_fields=changed)
    return _thread_response(request, ticket)


@require_POST
def reply(request, reference):
    """FR-012: a public reply, delivered by email and recorded on the thread."""
    ticket = get_object_or_404_for_user(Ticket, request.user, reference=reference)
    body = request.POST.get("body", "").strip()
    if not body:
        return HttpResponse(_("A reply cannot be empty."), status=422)

    with transaction.atomic():
        message = Message.objects.create(
            ticket=ticket,
            author=request.user,
            direction=Message.Direction.OUTBOUND,
            visibility=Message.Visibility.PUBLIC,
            channel=Ticket.Channel.EMAIL,
            body=body,
            delivery_status=Message.DeliveryStatus.PENDING,
        )
        updates = []
        if ticket.first_response_at is None:
            ticket.first_response_at = timezone.now()
            updates.append("first_response_at")
        if ticket.status == Ticket.Status.NEW:
            ticket.status = Ticket.Status.OPEN
            updates.append("status")
        if updates:
            ticket.save(update_fields=updates)

    # FR-016: a delivery failure is recorded on the message and shown on the ticket; it must
    # not fail the request that created it, or the agent loses the reply they just wrote.
    try:
        send_ticket_reply_email.delay(message_id=message.pk)
    except Exception:
        logger.exception("Queueing the reply email failed for message %s", message.pk)

    ticket.refresh_from_db()
    return _thread_response(request, ticket)


@require_POST
def note(request, reference):
    """FR-014, FR-015: an internal note. Never emailed, never customer-visible."""
    ticket = get_object_or_404_for_user(Ticket, request.user, reference=reference)
    body = request.POST.get("body", "").strip()
    if not body:
        return HttpResponse(_("A note cannot be empty."), status=422)

    Message.objects.create(
        ticket=ticket,
        author=request.user,
        direction=Message.Direction.OUTBOUND,
        visibility=Message.Visibility.INTERNAL,
        channel=ticket.origin_channel,
        body=body,
        delivery_status=Message.DeliveryStatus.NOT_APPLICABLE,
    )
    return _thread_response(request, ticket)
