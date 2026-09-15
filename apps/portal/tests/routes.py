"""
Route enumeration shared by the refusal tests (T007, T009).

Routes are discovered from the URL configuration rather than listed, so a view added next
month is covered on the day it is added rather than on the day somebody remembers. This
project has already shipped a catalog check that reported clean on a file it was not
reading; a hand-written list of staff routes would be the same mistake with worse
consequences.
"""

from typing import Any

from django.conf import settings
from django.urls import NoReverseMatch, get_resolver, reverse
from django.urls.resolvers import URLPattern, URLResolver

# Tried in order until one reverses. Every route in this product takes either nothing, one
# integer, or a ticket reference.
CANDIDATE_ARGS: tuple[list[Any], ...] = ([], [1], ["TCK-2026-0001"], ["X"], [1, 1])


def _named_patterns(resolver, namespace=None):
    for pattern in resolver.url_patterns:
        if isinstance(pattern, URLResolver):
            yield from _named_patterns(pattern, pattern.namespace or namespace)
        elif isinstance(pattern, URLPattern) and pattern.name:
            yield (f"{namespace}:{pattern.name}" if namespace else pattern.name)


def all_route_names():
    return sorted(set(_named_patterns(get_resolver())))


def url_for(name):
    for args in CANDIDATE_ARGS:
        try:
            return reverse(name, args=args)
        except NoReverseMatch:
            continue
    return None


def staff_routes():
    """Every route that is not the portal's and not deliberately public.

    The public set is `settings.LOGIN_EXEMPT_URL_NAMES`, which is the same list the
    deny-by-default middleware reads and which `apps/accounts/tests/test_anonymous_access.py`
    pins exactly — so a route cannot quietly leave this set without that test noticing.
    """
    routes = {}
    for name in all_route_names():
        if name.startswith("portal:") or name in settings.LOGIN_EXEMPT_URL_NAMES:
            continue
        url = url_for(name)
        if url:
            routes[name] = url
    return routes


def portal_routes():
    routes = {}
    for name in all_route_names():
        if not name.startswith("portal:"):
            continue
        url = url_for(name)
        if url:
            routes[name] = url
    return routes
