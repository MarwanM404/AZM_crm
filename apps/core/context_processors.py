"""
Context every authenticated screen needs, supplied once.

There is exactly one entry here and it earns its place by the alternative: the scope notice
(FR-004) belongs on every scoped screen, and adding it view by view means adding it to every
future view too. A screen that forgets it goes back to looking empty for no stated reason,
which is the defect this feature exists to close — and the forgetting would be silent.
"""

from apps.accounts.models import Branch, Department


def scope_notice(request):
    """Whether the viewer's own account is the reason their screens are empty.

    Cheap on purpose: no query at all for the ordinary case, because this runs on every
    authenticated request and the ordinary case is an account that has a scope.
    """
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    if user.department_id and user.branch_id:
        return {"viewer_has_no_scope": False}

    return {
        "viewer_has_no_scope": True,
        # Only loaded when the notice will actually render, and only for an administrator,
        # who is the only role that can act on it.
        "scope_departments": (
            Department.objects.filter(is_active=True).order_by("name")
            if user.role == user.Role.ADMINISTRATOR
            else []
        ),
        "scope_branches": (
            Branch.objects.filter(is_active=True).order_by("name")
            if user.role == user.Role.ADMINISTRATOR
            else []
        ),
    }
