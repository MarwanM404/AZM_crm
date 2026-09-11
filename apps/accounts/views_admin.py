"""
Administration screens: staff accounts, their scope, and deactivation (FR-025, FR-026).

Scoped like everything else — an administrator manages their own department and branch, not
the whole organization (FR-023 makes no exception for role).
"""

from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.accounts.models import Branch, Department, User
from apps.accounts.permissions import administrator_required
from apps.core.shortcuts import get_object_or_404_for_user


def _users_in_scope(request):
    return (
        User.objects.filter(department=request.user.department, branch=request.user.branch)
        .select_related("department", "branch")
        .order_by("full_name")
    )


@administrator_required
def user_list(request):
    return render(
        request,
        "accounts/users.html",
        {"section": "administration", "users": _users_in_scope(request)},
    )


@administrator_required
def user_new(request):
    departments = Department.objects.filter(is_active=True)
    branches = Branch.objects.filter(is_active=True)

    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        full_name = request.POST.get("full_name", "").strip()
        role = request.POST.get("role")
        department_id = request.POST.get("department")
        branch_id = request.POST.get("branch")

        if not email or not full_name:
            return HttpResponse(_("An email address and a name are required."), status=422)
        if role not in User.Role.values:
            return HttpResponse(_("Choose a role."), status=422)
        if not department_id or not branch_id:
            # FR-025: an account without a scope could see either everything or nothing;
            # both are wrong, so the account is not created at all.
            return HttpResponse(_("Choose a department and a branch."), status=422)
        if User.objects.filter(email=email).exists():
            return HttpResponse(_("An account with that email already exists."), status=422)

        user = User(
            email=email,
            full_name=full_name,
            role=role,
            department_id=department_id,
            branch_id=branch_id,
        )
        # No usable password: the account exists but cannot sign in until one is set,
        # so creating an account never creates a way in (FR-025).
        user.set_unusable_password()
        user.save()
        return redirect("administration:users")

    return render(
        request,
        "accounts/user_form.html",
        {
            "section": "administration",
            "departments": departments,
            "branches": branches,
            "roles": User.Role.choices,
        },
    )


@administrator_required
@require_POST
def user_scope(request, pk):
    user = get_object_or_404_for_user(User.objects.all(), request.user, pk=pk)
    department_id = request.POST.get("department")
    branch_id = request.POST.get("branch")
    if not department_id or not branch_id:
        return HttpResponse(_("Choose a department and a branch."), status=422)

    user.department_id = department_id
    user.branch_id = branch_id
    user.save(update_fields=["department", "branch"])
    return redirect("administration:users")


@administrator_required
@require_POST
def user_deactivate(request, pk):
    """FR-026: access ends on the next request, not at next sign-in. The session teardown
    lives on the model so it happens however the account is deactivated."""
    user = get_object_or_404_for_user(User.objects.all(), request.user, pk=pk)
    if user == request.user:
        return HttpResponse(_("You cannot deactivate your own account."), status=422)

    user.is_active = False
    user.save(update_fields=["is_active"])
    return redirect("administration:users")
