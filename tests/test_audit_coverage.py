"""
FR-027: every soft-deletable model must have an audit trail. This test discovers every
SoftDeleteModel subclass by introspection — it does not hand-maintain a list — so a new
soft-deletable model that is never registered in apps/core/audit.py fails the build instead
of relying on a reviewer to notice.
"""

import django.apps
from auditlog.registry import auditlog

from apps.core.audit import AUDITED_MODELS
from apps.core.models import SoftDeleteModel


def _all_soft_delete_models():
    return [
        model
        for model in django.apps.apps.get_models()
        if issubclass(model, SoftDeleteModel) and not model._meta.abstract
    ]


def test_every_soft_delete_model_is_registered_for_audit():
    unregistered = [m for m in _all_soft_delete_models() if m not in AUDITED_MODELS]
    assert not unregistered, (
        f"These soft-deletable models are not registered in apps/core/audit.py: "
        f"{[m.__name__ for m in unregistered]}"
    )


def test_audited_models_are_actually_registered_with_auditlog():
    for model in AUDITED_MODELS:
        assert auditlog.contains(model), f"{model.__name__} is not registered with auditlog"
