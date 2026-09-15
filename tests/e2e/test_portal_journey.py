"""
The customer portal end to end, in both languages (T095).

Every other test in this feature checks one thing. This one walks the whole path a real
customer walks — register, confirm from the message, sign in, raise a request, reply, sign
out, forget the password, reset, sign in again — because the screens can each be correct and
still not join up, and because that is what the twelve quickstart scenarios ask a person to do.

It does NOT replace the human pass. What it cannot judge is whether the Arabic reads naturally,
whether a message makes sense to somebody who did not build it, or whether the flow feels like
one product. quickstart.md records which scenarios still need a person and why.

Run in both languages, not one. Arabic is not a translation of this product, it is half of it,
and a journey that works in English and fails in Arabic fails for most of its users.
"""

import pytest
from django.core import mail

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]

PASSWORD = "a-long-enough-passphrase-42"
REPLACEMENT = "a-different-long-passphrase-77"


def link_containing(fragment):
    """The one link in the most recent message. Mail is sent by the live server on its own
    thread, and locmem's outbox is a module-level list, so the test process sees it."""
    assert mail.outbox, "no message was sent"
    for word in mail.outbox[-1].body.split():
        if fragment in word:
            return word.rstrip(".,")
    raise AssertionError(f"no {fragment} link in:\n{mail.outbox[-1].body}")


def choose(page, live_server, language):
    page.goto(f"{live_server.url}/portal/sign-in/")
    page.click(f".lang button[value='{language}']")
    page.wait_for_load_state("networkidle")


@pytest.mark.parametrize("language", ["en", "ar"])
def test_a_customer_can_get_in_ask_and_get_back_in(
    page, live_server, arabic_agent, settings, language
):
    from apps.tickets.models import Category, Ticket

    settings.PORTAL_BASE_URL = live_server.url
    Category.objects.create(
        name="Logistics", name_ar="الخدمات اللوجستية", department=arabic_agent.department
    )
    address = f"journey.{language}@example.com"

    choose(page, live_server, language)

    # 1. Register, and confirm from the message.
    page.goto(f"{live_server.url}/portal/register/")
    page.fill("input[name=email]", address)
    page.fill("input[name=password]", PASSWORD)
    mail.outbox.clear()
    page.click(".portal__form button[type=submit]")
    page.wait_for_load_state("networkidle")

    page.goto(link_containing("/confirm/"))
    page.wait_for_load_state("networkidle")
    assert "/sign-in/" not in page.url, "confirming did not sign the customer in"

    # 2. Raise a request, without being asked who they are.
    page.goto(f"{live_server.url}/portal/requests/new/")
    assert page.query_selector("input[name=email]") is None, "the form asked for the address"
    page.select_option("select[name=category]", index=1)
    page.fill("input[name=subject]", "A journey subject")
    page.fill("textarea[name=description]", "Something has gone wrong and I need help.")
    page.click(".portal__form button[type=submit]")
    page.wait_for_load_state("networkidle")

    ticket = Ticket.objects.get(subject="A journey subject")
    assert ticket.origin_channel == Ticket.Channel.PORTAL

    # 3. Reply to it.
    page.fill(".reply textarea", "One more thing I forgot to mention.")
    page.click(".reply button[type=submit]")
    page.wait_for_load_state("networkidle")
    assert "One more thing I forgot to mention." in page.inner_text("body")

    # 4. It is in their list.
    page.goto(f"{live_server.url}/portal/")
    page.wait_for_load_state("networkidle")
    assert ticket.reference in page.inner_text("body")

    # 5. Sign out, forget the password, reset it.
    page.click(".portal__signout button")
    page.wait_for_load_state("networkidle")

    page.goto(f"{live_server.url}/portal/reset/")
    page.fill("input[name=email]", address)
    mail.outbox.clear()
    page.click(".portal__form button[type=submit]")
    page.wait_for_load_state("networkidle")

    page.goto(link_containing("/new-password/"))
    page.fill("input[name=password]", REPLACEMENT)
    page.click(".portal__form button[type=submit]")
    page.wait_for_load_state("networkidle")
    assert "/sign-in/" not in page.url, "the reset did not sign the customer in"

    # 6. And the new password works from a clean start.
    page.context.clear_cookies()
    page.goto(f"{live_server.url}/portal/sign-in/")
    page.fill("input[name=email]", address)
    page.fill("input[name=password]", REPLACEMENT)
    page.click(".portal__form button[type=submit]")
    page.wait_for_load_state("networkidle")

    assert ticket.reference in page.inner_text(
        "body"
    ), "after the whole journey the customer cannot see the request they raised"


@pytest.mark.parametrize("language", ["en", "ar"])
def test_the_old_password_is_dead_afterwards(page, live_server, arabic_agent, settings, language):
    """Split out because it is the assertion somebody would drop as redundant, and it is the
    one the reset exists for."""
    from apps.portal.models import CustomerAccount

    settings.PORTAL_BASE_URL = live_server.url
    address = f"dead.{language}@example.com"
    account = CustomerAccount.objects.create_account(
        email=address, password=PASSWORD, language=language
    )
    account.confirm()

    choose(page, live_server, language)
    page.goto(f"{live_server.url}/portal/reset/")
    page.fill("input[name=email]", address)
    mail.outbox.clear()
    page.click(".portal__form button[type=submit]")
    page.wait_for_load_state("networkidle")

    page.goto(link_containing("/new-password/"))
    page.fill("input[name=password]", REPLACEMENT)
    page.click(".portal__form button[type=submit]")
    page.wait_for_load_state("networkidle")

    page.context.clear_cookies()
    page.goto(f"{live_server.url}/portal/sign-in/")
    page.fill("input[name=email]", address)
    page.fill("input[name=password]", PASSWORD)
    page.click(".portal__form button[type=submit]")
    page.wait_for_load_state("networkidle")

    assert "/portal/sign-in/" in page.url, "the old password still signs the customer in"
