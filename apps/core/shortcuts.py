"""
Scope-aware lookup helper.

FR-024: a record outside the acting user's scope MUST NOT be disclosed. A 403 confirms the
record exists; only a 404 does not. Every view that fetches a single scoped object by
identifier should use this rather than the raw ORM, so the 404-not-403 rule is enforced by
one function instead of by convention at every call site.
"""

from django.http import Http404
from django.shortcuts import get_object_or_404


def get_object_or_404_for_user(model_or_queryset, user, **kwargs):
    if hasattr(model_or_queryset, "objects"):
        queryset = model_or_queryset.objects.for_user(user)
    else:
        queryset = model_or_queryset

    try:
        return get_object_or_404(queryset, **kwargs)
    except Http404:
        raise
