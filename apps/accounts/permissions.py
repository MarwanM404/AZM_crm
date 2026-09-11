"""Role checks (FR-021, FR-022). Refused attempts are recorded (spec US4 scenario 2)."""

import logging

from django.core.exceptions import PermissionDenied

from apps.accounts.models import User

logger = logging.getLogger(__name__)


def require_administrator(request):
    if request.user.role != User.Role.ADMINISTRATOR:
        logger.warning(
            "Refused administrator action: user=%s path=%s", request.user.pk, request.path
        )
        raise PermissionDenied
