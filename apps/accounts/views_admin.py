"""
Administration screens: staff accounts, their scope, and deactivation (FR-025, FR-026).

Scoped like everything else — an administrator manages their own department and branch, not
the whole organization (FR-023 makes no exception for role).
"""

from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
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
    created = request.GET.get("created")
    return render(
        request,
        "accounts/users.html",
        {
            "section": "administration",
            "users": _users_in_scope(request),
            # Being present in a list of twenty is not confirmation that the work landed.
            "created_id": int(created) if created and created.isdigit() else None,
        },
    )


def _administers(request, department_id, branch_id) -> bool:
    """Whether the acting administrator could see an account placed in this scope.

    This is the question the add-account screen never asked. Scoping worked correctly the
    whole time — the account was created, in a department the administrator cannot look at,
    and nothing failed because nothing had gone wrong by the rules as written (FR-002).
    """
    return str(department_id) == str(request.user.department_id) and str(branch_id) == str(
        request.user.branch_id
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
        if not _administers(request, department_id, branch_id):
            # Refused rather than corrected. Quietly moving the account into the
            # administrator's own scope would also make it visible — and would be a second
            # outcome they were not told about, which is the defect this is fixing (FR-020).
            return HttpResponse(
                _(
                    "That department and branch are not yours to administer, and an account "
                    "created there would not be visible to you. It has not been created."
                ),
                status=422,
            )
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
        # Named in the redirect so the list can mark the row. Carried in the URL rather than
        # stored, so it marks this visit and not this account: a badge that persisted would
        # stop meaning "new" by the second visit.
        return redirect(f"{reverse('administration:users')}?created={user.pk}")

    return render(
        request,
        "accounts/user_form.html",
        {
            "section": "administration",
            "departments": departments,
            "branches": branches,
            "roles": User.Role.choices,
            # The administrator's own scope, so the field starts where their work actually
            # lands rather than on whichever department happens to sort first.
            "selected_department": request.user.department_id,
            "selected_branch": request.user.branch_id,
        },
    )


@administrator_required
@require_POST
def user_scope(request, pk):
    """Move an account to another department or branch (MVP FR-025).

    Deliberately NOT refused when the destination is outside the administrator's own scope,
    unlike `user_new`. The two look like the same rule and are not: moving someone to another
    department is the operation working, and losing sight of them afterwards is the point.
    Creating someone there is an accident nobody intended.

    It is still an action whose result the acting user cannot see (FR-020), so it should say
    so at the time. That needs a confirmation step, which is more than this story covers — it
    is recorded in the tasks rather than smuggled in here.
    """
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


@administrator_required
@require_POST
def own_scope(request):
    """Let an administrator with NO scope give themselves one (FR-005).

    The only place in this product where somebody changes their own scope, and a deliberate
    narrowing rather than an exception. Everywhere else scope is administered by somebody
    else, which works until the case that produced this defect: one administrator, no scope,
    and nobody who could fix it. Requiring a second, already-scoped administrator assumes one
    exists, and on a new installation none does.

    Permitted only from *no* scope. Once used it closes behind itself, because the account is
    no longer scopeless — an administrator who has a scope is in the ordinary case and the
    ordinary rule applies.
    """
    if request.user.department_id or request.user.branch_id:
        return HttpResponse(
            _(
                "Your account already has a department and a branch. Ask another "
                "administrator to change them."
            ),
            status=422,
        )

    department_id = request.POST.get("department")
    branch_id = request.POST.get("branch")
    if not department_id or not branch_id:
        return HttpResponse(_("Choose a department and a branch."), status=422)

    request.user.department_id = department_id
    request.user.branch_id = branch_id
    request.user.save(update_fields=["department", "branch"])
    return redirect("administration:users")
