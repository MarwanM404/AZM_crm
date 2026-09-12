"""
Role checks (MVP FR-021, FR-022; live chat FR-037).

Every check here names the roles it **allows**. That is not a style preference: with three
roles, a check written as "not an Agent" admits Supervisors to whatever it protects, silently
and with nothing failing. `apps/accounts/tests/test_supervisor_role.py` scans for that shape.

Refused attempts are recorded. An unrecorded refusal tells you nothing when you are trying to
work out who tried what.
"""

import functools
import logging

from django.core.exceptions import PermissionDenied

from apps.accounts.models import User

logger = logging.getLogger(__name__)

#: Administration — accounts, scope, the audit log. Not coaching.
ADMINISTRATIVE_ROLES = frozenset({User.Role.ADMINISTRATOR})

#: Observing a live conversation and whispering to the agent handling it. An Administrator is
#: included because they can already see everything; a Supervisor exists for people who should
#: coach *without* that.
OBSERVER_ROLES = frozenset({User.Role.SUPERVISOR, User.Role.ADMINISTRATOR})


def _refuse(request, required):
    logger.warning(
        "Refused action: user=%s role=%s path=%s required=%s",
        request.user.pk,
        request.user.role,
        request.path,
        sorted(required),
    )
    raise PermissionDenied


def _require(request, allowed):
    if request.user.role not in allowed:
        _refuse(request, allowed)


def require_administrator(request):
    _require(request, ADMINISTRATIVE_ROLES)


def require_observer(request):
    """Supervisors and Administrators. Used by the chat supervision views (FR-020)."""
    _require(request, OBSERVER_ROLES)


def can_observe(user):
    """Non-raising form, for deciding whether to show a control at all."""
    return user.is_authenticated and user.role in OBSERVER_ROLES


def administrator_required(view):
    @functools.wraps(view)
    def wrapped(request, *args, **kwargs):
        _require(request, ADMINISTRATIVE_ROLES)
        return view(request, *args, **kwargs)

    return wrapped


def observer_required(view):
    @functools.wraps(view)
    def wrapped(request, *args, **kwargs):
        _require(request, OBSERVER_ROLES)
        return view(request, *args, **kwargs)

    return wrapped
