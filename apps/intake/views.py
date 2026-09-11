"""
Public intake views (FR-001 to FR-006; contracts/http-endpoints.md).

Public and exempt from authentication (settings.LOGIN_EXEMPT_URL_NAMES). Creation is wrapped
in one transaction so a partial failure never leaves an orphaned contact or ticket.
"""

import time

from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import translation
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit

from apps.accounts.services.defaults import default_branch
from apps.customers.services.matching import find_or_create_contact
from apps.intake.forms import IntakeForm
from apps.messaging.tasks import send_confirmation_email
from apps.tickets.models import Ticket


@require_http_methods(["GET", "POST"])
@ratelimit(key="ip", rate="20/h", block=False)
@ratelimit(key="post:email", rate="5/h", block=False)
def request_form(request):
    """FR-006: rate limiting fails OPEN (block=False + manual check with a safe default) —
    a Redis outage must not turn away genuine customers, only stop protecting against abuse
    while it lasts (research.md #6)."""
    was_limited = getattr(request, "limited", False)

    if request.method == "POST" and not was_limited:
        form = IntakeForm(request.POST, initial={"rendered_at": time.time()})
        if form.is_valid():
            language = translation.get_language() or "ar"
            with transaction.atomic():
                branch = default_branch()
                department = form.cleaned_data["category"].department
                contact, _created = find_or_create_contact(
                    full_name=form.cleaned_data["full_name"],
                    email=form.cleaned_data["email"],
                    department=department,
                    branch=branch,
                )
                if _created:
                    contact.preferred_language = language
                    contact.save(update_fields=["preferred_language"])
                ticket = Ticket.objects.create(
                    contact=contact,
                    organization=contact.organization,
                    subject=form.cleaned_data["subject"],
                    description=form.cleaned_data["description"],
                    category=form.cleaned_data["category"],
                    origin_channel=Ticket.Channel.WEB_FORM,
                    department=department,
                    branch=branch,
                )
            send_confirmation_email.delay(
                contact_id=contact.pk, ticket_reference=ticket.reference, language=language
            )
            return redirect("intake:submitted", reference=ticket.reference)
    else:
        form = IntakeForm(initial={"rendered_at": time.time()})

    return render(request, "intake/form.html", {"form": form})


def submitted(request, reference):
    """Discloses only the reference (FR-004). No lookup of the ticket itself, so this cannot
    leak any stored customer data even to the person who just submitted it under a race."""
    get_object_or_404(Ticket.objects.filter(reference=reference).only("id"))
    return render(request, "intake/submitted.html", {"reference": reference})
