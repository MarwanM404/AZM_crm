"""
Role checks (FR-021, FR-022).

Two forms of the same rule: a guard to call inside a view, and a decorator to wrap one.
Both record the refused attempt (spec US4 scenario 2) — an unrecorded refusal tells you
nothing when you are trying to work out who tried what.
"""

import functools
import logging

from django.core.exceptions import PermissionDenied

from apps.accounts.models import User

logger = logging.getLogger(__name__)


def _refuse(request):
    logger.warning("Refused administrator action: user=%s path=%s", request.user.pk, request.path)
    raise PermissionDenied


def require_administrator(request):
    if request.user.role != User.Role.ADMINISTRATOR:
        _refuse(request)


def administrator_required(view):
    """Wrap a view so only administrators reach it. Authentication itself is already
    guaranteed by LoginRequiredMiddleware, so this only has to decide the role."""

    @functools.wraps(view)
    def wrapped(request, *args, **kwargs):
        if request.user.role != User.Role.ADMINISTRATOR:
            _refuse(request)
        return view(request, *args, **kwargs)

    return wrapped
