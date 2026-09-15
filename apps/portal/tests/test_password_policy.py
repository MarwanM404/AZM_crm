"""
T029. A password the customer chose, held to a standard (FR-005, FR-006).

This is the first place in the product where somebody outside the organization chooses a
credential. Staff passwords are set by an administrator, so the validators in
settings.AUTH_PASSWORD_VALIDATORS have never actually been applied to a password anybody
picked for themselves — they are configured and untested against real use.

The refusal has to say why. "Invalid password" sends people to try another password of the
same shape, and then another, and they end up choosing something worse than they started
with because the only feedback was no.
"""

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.portal.models import CustomerAccount
from apps.portal.services import passwords

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "password,why",
    [
        ("short", "too short"),
        ("password", "one of the most common passwords in the world"),
        ("12345678", "all numbers, and a famous one"),
        ("", "empty"),
    ],
)
def test_a_weak_password_is_refused(client, password, why):
    client.post(reverse("portal:register"), {"email": "noura@example.com", "password": password})

    assert not CustomerAccount.objects.filter(
        email="noura@example.com"
    ).exists(), f"A password that is {why} was accepted."


def test_the_refusal_says_what_is_wrong(client):
    response = client.post(
        reverse("portal:register"), {"email": "noura@example.com", "password": "password"}
    )
    body = response.content.decode()

    assert response.status_code == 200, "A refusal should redisplay the form, not redirect."
    assert "password" in body.lower()
    assert len(body) > 0
    errors = response.context["form"].errors.get("password")
    assert errors, "The form was refused without telling the customer which field, or why."


def test_a_password_like_the_address_is_refused(client):
    """UserAttributeSimilarityValidator, which needs an object carrying the attributes it
    compares against. Passing it nothing is the easy mistake, and it fails silently: the
    validator simply finds nothing to compare and approves everything."""
    client.post(
        reverse("portal:register"),
        {"email": "noura.alharbi@example.com", "password": "noura.alharbi"},
    )

    assert not CustomerAccount.objects.filter(email="noura.alharbi@example.com").exists()


def test_a_good_password_is_accepted(client):
    """So the policy cannot be satisfied by refusing everything — which would pass every test
    above and make the portal unusable."""
    client.post(
        reverse("portal:register"),
        {"email": "noura@example.com", "password": "a-long-enough-passphrase-42"},
    )

    assert CustomerAccount.objects.filter(email="noura@example.com").exists()


def test_the_policy_is_the_products_configured_one(settings):
    """Not a second policy written here. A portal with its own rules drifts from the staff
    application's, and then there are two answers to "how strong must a password be"."""
    settings.AUTH_PASSWORD_VALIDATORS = [
        {
            "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
            "OPTIONS": {"min_length": 40},
        }
    ]

    with pytest.raises(ValidationError):
        passwords.validate("a-long-enough-passphrase-42", email="noura@example.com")


def test_it_is_not_stored_in_the_clear(client):
    client.post(
        reverse("portal:register"),
        {"email": "noura@example.com", "password": "a-long-enough-passphrase-42"},
    )
    account = CustomerAccount.objects.get(email="noura@example.com")

    assert "a-long-enough-passphrase-42" not in account.password
    assert account.check_password("a-long-enough-passphrase-42")
