"""
The audit log viewer (FR-028, FR-029).

Read-only by construction: this module exposes one view, it renders a list, and there is no
route anywhere that writes a LogEntry. That is what makes FR-028 structural rather than a
promise — see apps/core/tests/test_audit_immutability.py, which sweeps the URL conf for any
route that could modify one.
"""

from auditlog.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import render
from django.utils.dateparse import parse_date

from apps.accounts.models import User
from apps.accounts.permissions import administrator_required
from apps.core.audit import AUDITED_MODELS

PAGE_SIZE = 100


@administrator_required
def audit_log(request):
    entries = LogEntry.objects.select_related("actor", "content_type").order_by("-timestamp")

    if entity := request.GET.get("entity"):
        entries = entries.filter(content_type__model=entity)
    if actor_id := request.GET.get("actor"):
        entries = entries.filter(actor_id=actor_id)

    # An unparseable date is ignored rather than raising: a mistyped filter should narrow
    # nothing, not break the page an administrator is using to investigate something.
    if start := parse_date(request.GET.get("from", "") or ""):
        entries = entries.filter(timestamp__date__gte=start)
    if end := parse_date(request.GET.get("to", "") or ""):
        entries = entries.filter(timestamp__date__lte=end)

    audited_types = ContentType.objects.get_for_models(*AUDITED_MODELS).values()

    return render(
        request,
        "core/audit_log.html",
        {
            "section": "administration",
            "entries": entries[:PAGE_SIZE],
            "entities": sorted(ct.model for ct in audited_types),
            "actors": User.objects.filter(
                department=request.user.department, branch=request.user.branch
            ).order_by("full_name"),
            "filters": request.GET,
            "actions": dict(LogEntry.Action.choices),
        },
    )
