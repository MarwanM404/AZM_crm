"""
T009. The boundary from the other side (FR-030).

Less dangerous than the reverse and worth having anyway. A staff session reaching the portal
would not leak anything to an outsider, but it would mean one session type satisfies both
sides — and a product where "signed in" is enough for either side is one change away from
being a product where it is enough for both.
"""

import pytest
from django.urls import reverse

from apps.portal.tests.routes import portal_routes

pytestmark = pytest.mark.django_db


def test_there_are_portal_routes_to_refuse():
    """Without this, the test below iterates an empty dictionary and passes having checked
    nothing — the failure this project has met often enough to guard against by habit."""
    assert portal_routes(), (
        "No portal routes were discovered, so the refusal test below is vacuous. If the "
        "portal genuinely has no routes yet, this feature is not ready for this check."
    )


def test_a_staff_session_reaches_no_portal_route(agent_client):
    for name, url in portal_routes().items():
        response = agent_client.get(url)

        assert response.status_code == 403, (
            f"{name} ({url}) answered an agent with {response.status_code}. The portal is not "
            "a staff application and a staff session must not satisfy it."
        )


def test_an_administrator_is_refused_too(admin_client_):
    """Administrators are the role most likely to be given an exception by someone being
    helpful. They are customers of this product, not customers of the company."""
    for name, url in portal_routes().items():
        assert admin_client_.get(url).status_code == 403, f"{name} ({url}) served an administrator"


def test_the_refusal_explains_itself(english_agent_client):
    """Not just refused — told why, and told their session is intact.

    A bare 403 sends a colleague to try a private window, find that it works, and conclude
    the portal is flaky rather than separate. Spec 003 FR-020 calls the general shape
    succeeding unhelpfully; this is the refusing equivalent.

    An English-speaking agent, because the assertion names an English string. Written first
    with the ordinary `agent` fixture — whose language defaults to Arabic — it passed only
    because the .mo files had not been compiled yet, and failed the moment they were. That is
    the same trap this project met in CI, arriving from the other side.
    """
    body = english_agent_client.get(reverse("portal:home")).content.decode()

    assert "customer portal" in body.lower()
    assert reverse("tickets:queue") in body, "There is no way back to the staff application."


def test_the_refusal_is_explained_in_arabic_too(agent_client):
    """The `agent` fixture speaks Arabic. A refusal page that is only written in English is a
    page half this product's staff cannot read."""
    body = agent_client.get(reverse("portal:home")).content.decode()

    assert "بوابة العملاء" in body, "The refusal was served to an Arabic agent in English."


def test_the_staff_session_survives_the_refusal(agent_client, agent):
    """The option that must never be taken: signing the agent out.

    A portal link a customer emails an agent would then end that agent's working session —
    a denial of service delivered by email, triggered by a helpful customer.
    """
    agent_client.get(reverse("portal:home"))

    assert agent_client.session.get("_auth_user_id") == str(agent.pk)
    assert agent_client.get(reverse("tickets:queue")).status_code == 200


def test_the_explanation_is_not_a_portal_template():
    """The premise the internal-message sweep rests on.

    templates/portal/ is swept by directory rather than by a list, which is only sound while
    everything in it is customer-facing. A staff-facing page inside it would make the rule
    "everything here is customer-facing, except what is not" — the position templates/chat/
    is already in, where every file must be classified by hand.
    """
    from pathlib import Path

    portal_templates = Path(__file__).resolve().parents[3] / "templates" / "portal"

    assert not (portal_templates / "portal_is_for_customers.html").exists()
    assert (portal_templates.parent / "core" / "portal_is_for_customers.html").exists()
