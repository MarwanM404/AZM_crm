"""FR-033: a user's language choice survives reload and subsequent sign-ins."""

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_switching_language_persists_on_the_user_record(agent_client, agent):
    assert agent.language == "ar"

    response = agent_client.post(reverse("accounts:language"), {"language": "en"})
    assert response.status_code == 204

    agent.refresh_from_db()
    assert agent.language == "en"


@pytest.mark.django_db
def test_choice_survives_a_fresh_sign_in(client, agent):
    client.force_login(agent)
    client.post(reverse("accounts:language"), {"language": "en"})

    client.logout()
    client.force_login(agent)

    agent.refresh_from_db()
    assert agent.language == "en"  # stored on the account, not only the session


@pytest.mark.django_db
def test_invalid_language_is_rejected(agent_client, agent):
    response = agent_client.post(reverse("accounts:language"), {"language": "fr"})
    assert response.status_code == 400

    agent.refresh_from_db()
    assert agent.language == "ar"


@pytest.mark.django_db
def test_pages_render_in_the_users_stored_language(client, agent):
    """The stored preference must actually drive rendering, not just sit in the database."""
    agent.language = "ar"
    agent.save(update_fields=["language"])
    client.force_login(agent)

    body = client.get(reverse("tickets:queue")).content.decode()
    assert 'dir="rtl"' in body
    assert "قائمة التذاكر" in body
