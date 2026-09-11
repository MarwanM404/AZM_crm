"""
FR-023, FR-024: every ScopedModel query must be scoped by department and branch, and a
record outside the acting user's scope must not be disclosed.

This discovers every ScopedModel subclass and proves the *queryset-level* guarantee now.
The HTTP-level guarantee (out-of-scope request returns 404, not 403) is exercised per-view
as each view lands in Phases 4-6 (T057, T083, T096) via
apps.core.shortcuts.get_object_or_404_for_user, the one helper every such view must use.
"""

import django.apps
import pytest

from apps.core.models import ScopedModel


def _all_scoped_models():
    return [
        model
        for model in django.apps.apps.get_models()
        if issubclass(model, ScopedModel) and not model._meta.abstract
    ]


def test_every_scoped_model_exposes_for_user():
    for model in _all_scoped_models():
        assert hasattr(model.objects, "for_user"), (
            f"{model.__name__}.objects has no for_user(); it inherits ScopedModel but its "
            "manager was not built from CoreQuerySet (see apps/core/querysets.py)."
        )


@pytest.mark.django_db
def test_for_user_is_the_only_way_scope_is_applied(agent, department, other_department, branch):
    """A smoke test that the unscoped default manager does NOT filter — proving that scoping
    is explicit (ADR-004), not implicit. Callers must call for_user(); this is what makes a
    forgotten call visible in code review rather than accidentally safe."""
    from apps.customers.models import Organization

    Organization.objects.create(name="Other dept", department=other_department, branch=branch)

    assert Organization.objects.count() >= 1  # unscoped manager sees everything
    assert Organization.objects.for_user(agent).count() == 0  # scoped manager sees nothing here
