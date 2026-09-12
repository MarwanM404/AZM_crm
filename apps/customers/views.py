"""
Customer organizations, contacts, notes, and the unlinked-contact queue.

Every view reads through `for_user()` or `get_object_or_404_for_user()`, so an out-of-scope
record returns 404 rather than 403 (FR-024).
"""

from django.contrib import messages
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.accounts.permissions import require_administrator
from apps.attachments.services.uploads import attach_to_note
from apps.core.shortcuts import get_object_or_404_for_user
from apps.customers.models import Contact, Note, Organization
from apps.customers.services.linking import link_contact
from apps.customers.services.timeline import timeline_for

PAGE_SIZE = 50


def organization_list(request):
    # Counted in the database, not per row in the template: `organization.contacts.count`
    # inside a loop is one query per organization (T136).
    organizations = (
        Organization.objects.for_user(request.user)
        .annotate(
            contact_count=Count("contacts", distinct=True),
            ticket_count=Count("tickets", distinct=True),
        )
        .order_by("name")[:PAGE_SIZE]
    )
    return render(
        request,
        "customers/list.html",
        {"section": "customers", "organizations": organizations},
    )


def organization_detail(request, pk):
    organization = get_object_or_404_for_user(Organization, request.user, pk=pk)
    contact = None
    if contact_id := request.GET.get("contact"):
        contact = Contact.objects.for_user(request.user).filter(pk=contact_id).first()

    context = {
        "section": "customers",
        "organization": organization,
        # Prefetched: the sidebar renders each contact's details, which is otherwise one
        # query per contact (T136).
        "contacts": organization.contacts.prefetch_related("details"),
        "entries": timeline_for(organization, contact=contact),
        "narrowed_to": contact,
    }
    if request.htmx:
        return render(request, "customers/partials/timeline.html", context)
    return render(request, "customers/detail.html", context)


@require_POST
def add_note(request, pk):
    organization = get_object_or_404_for_user(Organization, request.user, pk=pk)
    body = request.POST.get("body", "").strip()
    if not body:
        return HttpResponse(_("A note cannot be empty."), status=422)

    note = Note.objects.create(
        organization=organization,
        author=request.user,
        body=body,
        department=organization.department,
        branch=organization.branch,
    )
    _attached, upload_errors = attach_to_note(
        request.FILES.getlist("attachments"), note, request.user
    )
    if upload_errors:
        messages.warning(request, "; ".join(upload_errors))
    return redirect("customers:detail", pk=organization.pk)


def edit_organization(request, pk):
    organization = get_object_or_404_for_user(Organization, request.user, pk=pk)
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        if not name:
            return HttpResponse(_("A name is required."), status=422)
        organization.name = name
        organization.name_ar = request.POST.get("name_ar", "").strip()
        organization.save(update_fields=["name", "name_ar"])
        return redirect("customers:detail", pk=organization.pk)

    return render(
        request,
        "customers/edit.html",
        {"section": "customers", "organization": organization},
    )


@require_POST
def delete_organization(request, pk):
    """FR-020: soft deletion, recoverable and audited. Administrator only."""
    require_administrator(request)
    organization = get_object_or_404_for_user(Organization, request.user, pk=pk)
    organization.soft_delete(by=request.user)
    return redirect("customers:list")


def unlinked_contacts(request):
    """FR-041: contacts that arrived without a determinable employer, surfaced for staff."""
    contacts = (
        Contact.objects.for_user(request.user)
        .filter(organization__isnull=True)
        .prefetch_related("details")
        .order_by("-created_at")[:PAGE_SIZE]
    )

    # A shared email domain is a hint that these people work together — shown so staff can
    # judge, never acted on automatically (spec edge case).
    domains: dict[str, int] = {}
    for contact in contacts:
        for detail in contact.details.all():
            if detail.kind == detail.Kind.EMAIL and "@" in detail.value:
                domain = detail.value.split("@", 1)[1]
                domains[domain] = domains.get(domain, 0) + 1

    return render(
        request,
        "customers/unlinked.html",
        {
            "section": "customers",
            "contacts": contacts,
            "shared_domains": {d for d, count in domains.items() if count > 1},
            "organizations": Organization.objects.for_user(request.user).order_by("name"),
        },
    )


@require_POST
def link(request, pk):
    contact = get_object_or_404_for_user(Contact, request.user, pk=pk)

    if organization_id := request.POST.get("organization"):
        organization = (
            Organization.objects.for_user(request.user).filter(pk=organization_id).first()
        )
        if organization is None:
            return HttpResponse(_("Unknown organization."), status=422)
    elif name := request.POST.get("new_organization", "").strip():
        organization = Organization.objects.create(
            name=name, department=contact.department, branch=contact.branch
        )
    else:
        return HttpResponse(_("Choose an organization, or name a new one."), status=422)

    link_contact(contact, organization)
    return redirect("customers:detail", pk=organization.pk)


def edit_contact(request, pk):
    contact = get_object_or_404_for_user(Contact, request.user, pk=pk)
    if request.method == "POST":
        full_name = request.POST.get("full_name", "").strip()
        if not full_name:
            return HttpResponse(_("A name is required."), status=422)
        contact.full_name = full_name
        contact.preferred_language = request.POST.get(
            "preferred_language", contact.preferred_language
        )
        contact.save(update_fields=["full_name", "preferred_language"])
        if contact.organization_id:
            return redirect("customers:detail", pk=contact.organization_id)
        return redirect("customers:unlinked")

    return render(
        request,
        "customers/contact_edit.html",
        {"section": "customers", "contact": contact},
    )
