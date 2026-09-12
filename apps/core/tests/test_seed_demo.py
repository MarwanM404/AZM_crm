"""The seed command is real code that ships in the repository and breaks like any other —
usually when a model gains a required field."""

import pytest
from django.core.management import call_command

from apps.accounts.models import Branch, Department, User
from apps.customers.models import Organization
from apps.tickets.models import Category, Ticket


@pytest.mark.django_db
def test_seed_demo_creates_a_working_dataset():
    call_command("seed_demo")

    assert Department.objects.exists()
    assert Branch.objects.exists()
    assert Category.objects.exists()
    assert User.objects.filter(role=User.Role.AGENT).exists()
    assert User.objects.filter(role=User.Role.ADMINISTRATOR).exists()


@pytest.mark.django_db
def test_seed_demo_includes_arabic_content():
    """T126: Arabic in the seed data is what makes encoding and direction problems surface in
    development rather than at release."""
    call_command("seed_demo")

    arabic_tickets = [t for t in Ticket.objects.all() if any("؀" <= c <= "ۿ" for c in t.subject)]
    assert arabic_tickets, "no Arabic ticket in the seed data"
    assert Organization.objects.filter(name_ar__gt="").exists()


@pytest.mark.django_db
def test_seed_demo_is_idempotent():
    """Running it twice must not duplicate or fail — developers re-run it constantly."""
    call_command("seed_demo")
    before = (User.objects.count(), Ticket.objects.count(), Organization.objects.count())

    call_command("seed_demo")
    after = (User.objects.count(), Ticket.objects.count(), Organization.objects.count())

    assert before == after
