"""FR-026: deactivation terminates access immediately, not at next sign-in."""

import pytest
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session


@pytest.mark.django_db
def test_deactivating_a_user_deletes_their_active_sessions(agent):
    session = SessionStore()
    session["_auth_user_id"] = str(agent.pk)
    session["_auth_user_backend"] = "django.contrib.auth.backends.ModelBackend"
    session.set_expiry(3600)
    session.save()
    assert Session.objects.filter(session_key=session.session_key).exists()

    agent.is_active = False
    agent.save()

    assert not Session.objects.filter(session_key=session.session_key).exists()


@pytest.mark.django_db
def test_saving_an_already_inactive_user_does_not_error(agent):
    agent.is_active = False
    agent.save()
    agent.full_name = "Renamed"
    agent.save()  # must not raise, and must not attempt to re-terminate anything odd
