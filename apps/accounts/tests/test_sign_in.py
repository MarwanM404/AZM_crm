"""The sign-in form's failure paths — the half of authentication that is easy to leave
untested because the happy path is exercised by every other test's force_login."""

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_correct_credentials_sign_a_user_in(client, agent):
    agent.set_password("known-password")
    agent.save()

    response = client.post(
        reverse("accounts:sign_in"), {"email": agent.email, "password": "known-password"}
    )
    assert response.status_code == 302
    assert response.url == reverse("tickets:queue")


@pytest.mark.django_db
def test_wrong_password_is_refused_without_saying_which_field_was_wrong(client, agent):
    agent.set_password("known-password")
    agent.save()

    response = client.post(reverse("accounts:sign_in"), {"email": agent.email, "password": "wrong"})
    body = response.content.decode()

    assert response.status_code == 200
    assert "Invalid email or password" in body
    # Naming which half was wrong confirms whether an address has an account here.
    assert "no account" not in body.lower()


@pytest.mark.django_db
def test_unknown_email_gives_the_same_message(client, db):
    response = client.post(
        reverse("accounts:sign_in"), {"email": "nobody@example.com", "password": "whatever"}
    )
    assert "Invalid email or password" in response.content.decode()


@pytest.mark.django_db
def test_a_deactivated_account_cannot_sign_in(client, agent):
    agent.set_password("known-password")
    agent.is_active = False
    agent.save()

    response = client.post(
        reverse("accounts:sign_in"), {"email": agent.email, "password": "known-password"}
    )
    assert response.status_code == 200
    assert "Invalid email or password" in response.content.decode()


@pytest.mark.django_db
def test_signing_out_ends_the_session(agent_client):
    response = agent_client.post(reverse("accounts:sign_out"))
    assert response.status_code == 302

    after = agent_client.get(reverse("tickets:queue"))
    assert after.status_code == 302
    assert reverse("accounts:sign_in") in after.url
