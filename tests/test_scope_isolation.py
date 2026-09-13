"""
FR-023, FR-024: every scoped record is invisible outside its department and branch, and a
request for one returns 404 — never 403, which would confirm it exists.

Three layers, deliberately:

1. Every ScopedModel subclass is discovered by introspection and must expose `for_user`, so
   a new scoped model cannot quietly ship without the filter.
2. The queryset-level guarantee, proving scoping is explicit (ADR-004) rather than implicit.
3. The HTTP-level guarantee, swept across every route that addresses a single record, using
   real out-of-scope objects. This is the layer that catches a view reading through the raw
   manager instead of `get_object_or_404_for_user`.
"""

import django.apps
import pytest
from django.urls import reverse

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
    """The unscoped default manager does NOT filter — proving scoping is explicit (ADR-004).
    A forgotten `for_user()` must be visible in review, not accidentally safe."""
    from apps.customers.models import Organization

    Organization.objects.create(name="Other dept", department=other_department, branch=branch)

    assert Organization.objects.count() >= 1
    assert Organization.objects.for_user(agent).count() == 0


# --- HTTP layer: every route that addresses one record, with a real out-of-scope object ---


def _out_of_scope_routes(other_department, branch, contact):
    """Build one out-of-scope object per record-addressed route."""
    from apps.customers.models import Contact, Organization
    from apps.tickets.models import Category, Ticket

    org = Organization.objects.create(
        name="Out of scope Co", department=other_department, branch=branch
    )
    category = Category.objects.create(name="Out of scope", department=other_department)
    ticket = Ticket.objects.create(
        contact=contact,
        organization=org,
        subject="Out of scope ticket",
        description="...",
        category=category,
        origin_channel=Ticket.Channel.WEB_FORM,
        department=other_department,
        branch=branch,
    )
    stranger = Contact.objects.create(
        full_name="Out of scope person", department=other_department, branch=branch
    )

    conversation = _out_of_scope_conversation(other_department, branch, contact, category)

    return [
        ("GET", "tickets:detail", {"reference": ticket.reference}, None),
        ("POST", "tickets:take", {"reference": ticket.reference}, {}),
        ("POST", "tickets:status", {"reference": ticket.reference}, {"status": "OPEN"}),
        ("POST", "tickets:fields", {"reference": ticket.reference}, {"priority": "HIGH"}),
        ("POST", "tickets:reply", {"reference": ticket.reference}, {"body": "hello"}),
        ("POST", "tickets:note", {"reference": ticket.reference}, {"body": "hello"}),
        ("GET", "customers:detail", {"pk": org.pk}, None),
        ("GET", "customers:edit", {"pk": org.pk}, None),
        ("POST", "customers:note", {"pk": org.pk}, {"body": "hello"}),
        ("POST", "customers:link_contact", {"pk": stranger.pk}, {"new_organization": "X"}),
        ("GET", "customers:edit_contact", {"pk": stranger.pk}, None),
        # Live chat. A conversation is at least as disclosing as the ticket it belongs to:
        # it names a customer, what they are asking about, and which colleague is handling it.
        ("GET", "chat:conversation", {"pk": conversation.pk}, None),
        ("POST", "chat:attach", {"pk": conversation.pk}, {"ticket": ticket.pk}),
    ]


def _out_of_scope_conversation(other_department, branch, contact, category):
    from apps.chat.models import Conversation
    from apps.tickets.models import Ticket

    placeholder = Ticket.objects.create(
        contact=contact,
        subject="Out of scope conversation",
        description="",
        category=category,
        origin_channel=Ticket.Channel.CHAT,
        department=other_department,
        branch=branch,
    )
    return Conversation.objects.create(
        ticket=placeholder,
        contact=contact,
        visitor_token_hash="x",
        department=other_department,
        branch=branch,
    )


@pytest.mark.django_db
def test_every_record_route_returns_404_out_of_scope(
    agent_client, other_department, branch, contact
):
    failures = []
    for method, name, kwargs, data in _out_of_scope_routes(other_department, branch, contact):
        url = reverse(name, kwargs=kwargs)
        response = agent_client.get(url) if method == "GET" else agent_client.post(url, data or {})
        if response.status_code != 404:
            failures.append(f"{method} {name} -> {response.status_code} (expected 404)")

    assert not failures, (
        "These routes disclosed an out-of-scope record's existence (FR-024). A 403 confirms "
        "the record is real; only a 404 discloses nothing:\n  " + "\n  ".join(failures)
    )


@pytest.mark.django_db
def test_out_of_scope_response_body_leaks_nothing(agent_client, other_department, branch, contact):
    routes = _out_of_scope_routes(other_department, branch, contact)
    for method, name, kwargs, data in routes:
        url = reverse(name, kwargs=kwargs)
        response = agent_client.get(url) if method == "GET" else agent_client.post(url, data or {})
        body = response.content.decode()
        assert "Out of scope ticket" not in body
        assert "Out of scope Co" not in body
        assert "Out of scope person" not in body


# --- live chat: the sweep has to keep up with the routes (T124) ---


def _chat_record_routes():
    """Every chat route addressing one record by primary key.

    Read from the URLconf rather than listed by hand, so a new record-addressed chat route is
    covered the moment it is added. The failure this prevents is not a broken check — it is a
    route nobody remembered to check at all, which looks exactly like a passing suite.
    """
    from apps.chat import urls as chat_urls

    return sorted(
        pattern.name for pattern in chat_urls.urlpatterns if "<int:pk>" in str(pattern.pattern)
    )


SWEPT_BY_THE_AGENT_SWEEP = {"conversation", "attach"}
SWEPT_SEPARATELY_BECAUSE_ROLE_IS_CHECKED_FIRST = {"supervise_conversation"}


def test_every_chat_record_route_is_covered_somewhere():
    covered = SWEPT_BY_THE_AGENT_SWEEP | SWEPT_SEPARATELY_BECAUSE_ROLE_IS_CHECKED_FIRST
    missing = set(_chat_record_routes()) - covered

    assert not missing, (
        "These chat routes address a single record and are in no scope sweep. Add each to "
        "_out_of_scope_routes, or to the supervisor sweep if a role check runs before the "
        f"scope check: {sorted(missing)}"
    )


@pytest.mark.django_db
def test_supervision_of_an_out_of_scope_conversation_is_not_found(
    supervisor_client, other_department, branch, contact
):
    """Swept apart from the rest because `observer_required` runs before the scope lookup, so
    an Agent gets 403 on role grounds and would mask whether the scope check exists at all.

    A supervisor has the role and still must not see another department's conversation
    (FR-043) — and must not be able to tell "not yours" from "not there".
    """
    from apps.tickets.models import Category

    category = Category.objects.create(name="Out of scope chat", department=other_department)
    conversation = _out_of_scope_conversation(other_department, branch, contact, category)

    response = supervisor_client.get(
        reverse("chat:supervise_conversation", kwargs={"pk": conversation.pk})
    )
    absent = supervisor_client.get(reverse("chat:supervise_conversation", kwargs={"pk": 999999}))

    assert response.status_code == 404
    assert response.status_code == absent.status_code
    assert "Out of scope conversation" not in response.content.decode()
