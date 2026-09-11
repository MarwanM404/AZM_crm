"""
Celery task base requiring an explicit actor.

A Celery task has no HTTP request, so django-auditlog's request-based actor attribution
(apps/core/middleware.py's AuditlogMiddleware in settings) does not apply. Any task writing
to a customer record must set the actor explicitly, or the audit trail would attribute human-
initiated work to a system user, violating FR-027. This base makes that mistake fail loudly
rather than silently.
"""

from auditlog.context import set_actor
from celery import Task


class ActorRequiredTask(Task):
    """Subclass and call `self.run_as(actor, *args, **kwargs)`, or pass `actor` as the first
    positional argument to a task decorated with `base=ActorRequiredTask` and wrap the body
    in `with set_actor(actor):`."""

    def run_as(self, actor, *args, **kwargs):
        if actor is None:
            raise ValueError(
                f"{self.name} requires an explicit actor; background writes must not be "
                "attributed to a system user (FR-027)."
            )
        with set_actor(actor):
            return self.run(*args, **kwargs)
