"""FR-033: a user's language choice survives reload and subsequent sign-ins."""

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_switching_language_persists_on_the_user_record(agent_client, agent):
    assert agent.language == "ar"

    response = agent_client.post(reverse("accounts:language"), {"language": "en"})
    assert response.status_code == 302

    agent.refresh_from_db()
    assert agent.language == "en"


@pytest.mark.django_db
def test_switching_returns_to_the_page_you_were_on(agent_client, agent):
    """A 204 tells the browser to stay put and change nothing, so the switch appeared to do
    nothing until the page was reloaded by hand. It must come back to the same page, already
    in the new language."""
    response = agent_client.post(
        reverse("accounts:language"),
        {"language": "en", "next": reverse("customers:list")},
    )
    assert response.status_code == 302
    assert response.url == reverse("customers:list")

    followed = agent_client.get(response.url)
    assert 'dir="ltr"' in followed.content.decode()


@pytest.mark.django_db
def test_the_new_language_is_visible_immediately_after_following_the_redirect(agent_client, agent):
    before = agent_client.get(reverse("tickets:queue")).content.decode()
    assert "قائمة التذاكر" in before  # starts in Arabic

    response = agent_client.post(
        reverse("accounts:language"),
        {"language": "en", "next": reverse("tickets:queue")},
    )
    after = agent_client.get(response.url).content.decode()

    assert "Ticket queue" in after
    assert 'dir="ltr"' in after


@pytest.mark.django_db
def test_an_off_site_next_is_refused(agent_client, agent):
    """`next` comes from the request, so an unchecked redirect here is an open redirect."""
    response = agent_client.post(
        reverse("accounts:language"),
        {"language": "en", "next": "https://evil.example/phish"},
    )
    assert response.status_code == 302
    assert "evil.example" not in response.url
    assert response.url == reverse("tickets:queue")


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
