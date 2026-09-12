"""
Static assets must not be caught by the deny-by-default rule.

A stylesheet is not a view: it resolves to no URL name, so a naive "everything not named as
exempt is denied" check redirects it to sign-in. The page still renders — which is why this
is easy to miss — but with no CSS and no JavaScript, for anonymous visitors only. The public
request form is the one page whose entire audience is anonymous.
"""

import pytest
from django.conf import settings
from django.urls import reverse


@pytest.mark.django_db
def test_anonymous_visitor_is_not_redirected_away_from_static_files(client):
    response = client.get(f"{settings.STATIC_URL}css/base.css")
    assert response.status_code != 302, (
        "A static file was redirected to sign-in. Anonymous visitors would see the public "
        "request form with no styling at all."
    )


@pytest.mark.django_db
def test_the_public_form_still_requires_no_sign_in(client):
    assert client.get(reverse("intake:form")).status_code == 200


@pytest.mark.django_db
def test_application_paths_are_still_denied_by_default(client):
    response = client.get(reverse("tickets:queue"))
    assert response.status_code == 302
    assert reverse("accounts:sign_in") in response.url


@pytest.mark.django_db
def test_a_path_that_merely_starts_like_static_is_still_denied(client):
    """The exemption is a prefix check, so confirm it cannot be used as a way in."""
    response = client.get("/staticky-not-really/")
    assert response.status_code in (302, 404)
    if response.status_code == 302:
        assert reverse("accounts:sign_in") in response.url


@pytest.mark.django_db
def test_a_root_media_url_does_not_switch_authentication_off(client, settings):
    """Django's MEDIA_URL defaults to "/". A prefix check that accepts it exempts every path
    on the site — this is not hypothetical, it is what the first version of this fix did."""
    settings.MEDIA_URL = "/"

    response = client.get(reverse("tickets:queue"))
    assert response.status_code == 302, (
        "With MEDIA_URL='/', the asset exemption matched every path and authentication was "
        "off for the whole site."
    )
    assert reverse("accounts:sign_in") in response.url


@pytest.mark.django_db
def test_an_empty_static_url_does_not_exempt_everything(client, settings):
    settings.STATIC_URL = ""
    response = client.get(reverse("tickets:queue"))
    assert response.status_code == 302
