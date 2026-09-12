"""
The HTTP surface around the sockets (contracts/http-endpoints.md).

The conversation itself happens over WebSocket; these are what opens it, and what the public
site asks before deciding whether to show a chat launcher at all.
"""

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_http_methods

from apps.accounts.models import Branch, Department
from apps.chat.forms import PreChatForm
from apps.chat.models import Conversation
from apps.chat.services import lifecycle, presence, queue, unread
from apps.core.shortcuts import get_object_or_404_for_user
from apps.customers.services.matching import find_or_create_contact
from apps.tickets.services.visibility import staff_messages_for


def _default_scope():
    """Chat has no way to ask a visitor which department they need, so it lands in the same
    place the request form's default category would put it."""
    branch = Branch.objects.filter(is_active=True).order_by("pk").first()
    department = Department.objects.filter(is_active=True).order_by("pk").first()
    return department, branch


@require_GET
def availability(request):
    """Asked by the public site on every page load, so it stays a presence lookup and never
    becomes a query against conversation history (FR-001, FR-039)."""
    department, branch = _default_scope()
    if department is None or branch is None:
        return JsonResponse({"available": False})

    return JsonResponse({"available": lifecycle.anyone_available(department.pk, branch.pk)})


@require_http_methods(["GET"])
def widget(request):
    """The visitor panel. Renders the pre-chat form, or nothing at all when the desk is
    closed — FR-039: a queue behind nobody is a waiting room with no door."""
    department, branch = _default_scope()
    available = bool(department and branch and lifecycle.anyone_available(department.pk, branch.pk))
    return render(
        request,
        "chat/widget.html",
        {"form": PreChatForm(), "available": available},
    )


@require_http_methods(["POST"])
def start(request):
    """Create the conversation and hand back the visitor's token.

    When nobody is online the visitor is sent to the request form instead, carrying what they
    already typed (FR-018, FR-039).
    """
    department, branch = _default_scope()
    if department is None or branch is None:
        return JsonResponse({"available": False, "fallback": "/request/"}, status=503)

    if not lifecycle.anyone_available(department.pk, branch.pk):
        return JsonResponse(
            {
                "available": False,
                "fallback": "/request/",
                "carry": {
                    "full_name": request.POST.get("full_name", ""),
                    "email": request.POST.get("email", ""),
                    "subject": request.POST.get("subject", ""),
                },
            }
        )

    form = PreChatForm(request.POST)
    if not form.is_valid():
        return JsonResponse({"errors": form.errors}, status=422)

    contact, _created = find_or_create_contact(
        full_name=form.cleaned_data["full_name"],
        email=form.cleaned_data["email"],
        department=department,
        branch=branch,
    )
    conversation, token = lifecycle.start(
        contact=contact,
        department=department,
        branch=branch,
        category=form.cleaned_data["category"],
        subject=form.cleaned_data["subject"],
    )
    agent_id = lifecycle.try_assign(
        conversation, lifecycle.candidate_agents(department.pk, branch.pk)
    )

    return JsonResponse(
        {
            "available": True,
            "token": token,
            "conversation": conversation.pk,
            "assigned": bool(agent_id),
            "position": queue.position(str(conversation.pk), department.pk, branch.pk),
            # No ticket reference: it is given when the conversation ends, because the agent
            # may attach it to an existing ticket in between (FR-040).
        }
    )


@require_http_methods(["POST"])
def leave_queue(request):
    """FR-019: a visitor who closes the panel stops holding a place."""
    department, branch = _default_scope()
    conversation_id = request.POST.get("conversation")
    if conversation_id and department and branch:
        queue.leave(str(conversation_id), department.pk, branch.pk)
    return JsonResponse({"left": True})


# --- staff ---


@require_GET
def console(request):
    """The agent's multi-conversation console (FR-013, FR-015).

    Scoped like every other list in this product. Each conversation carries its own customer
    context, because an agent moving between three of them cannot hold three customers'
    histories in their head.
    """
    conversations = (
        Conversation.objects.for_user(request.user)
        .filter(assigned_to=request.user, state=Conversation.State.ACTIVE)
        .select_related("contact", "contact__organization", "ticket")
        .prefetch_related("contact__details")
        .order_by("-last_activity_at")
    )
    return render(
        request,
        "chat/console.html",
        {
            "section": "chat",
            "conversations": conversations,
            "unread": unread.all_for(request.user.pk),
            "online": presence.is_online(request.user.pk),
            "capacity": presence.capacity_remaining(request.user.pk),
        },
    )


@require_GET
def conversation_detail(request, pk):
    """One conversation with its history and the customer beside it.

    Out of scope is not found, never forbidden (MVP FR-024) — the same rule the ticket detail
    follows, applied here because a conversation is just as disclosing.
    """
    conversation = get_object_or_404_for_user(Conversation, request.user, pk=pk)
    unread.clear(request.user.pk, conversation.pk)

    return render(
        request,
        "chat/conversation.html",
        {
            "section": "chat",
            "conversation": conversation,
            "messages_": staff_messages_for(conversation.ticket).select_related("author"),
            "recent_tickets": conversation.contact.tickets.exclude(
                pk=conversation.ticket_id
            ).order_by("-created_at")[:5],
        },
    )
