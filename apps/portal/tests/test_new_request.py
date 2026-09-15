"""
T068-T070. A signed-in customer raises a request (FR-023, FR-025).

The smallest story in this feature and the one with the most ways to quietly break something
else, because it adds a second path through work the public form already does. Two properties
matter more than the new screen itself.

The customer is not asked who they are. They proved an address to get here, and a form that
asks for it again is both a worse experience and a worse guarantee: whatever they type into a
name-and-email box is unverified, and the system would be trusting it over the address it
actually checked.

And the public form keeps working exactly as it does today (FR-025). The way to get that is
not to test the portal carefully — it is for both paths to run the same code, so that the
anonymous form cannot drift without the portal drifting with it.
"""

import pytest
from django.urls import reverse

from apps.customers.models import Contact, ContactDetail
from apps.tickets.models import Ticket

pytestmark = pytest.mark.django_db


def raise_request(client, category, subject="A new problem", description="It started today."):
    return client.post(
        reverse("portal:new_request"),
        {"category": category.pk, "subject": subject, "description": description},
    )


def test_the_form_does_not_ask_who_they_are(customer_client, category):
    """FR-023, scenario 1."""
    response = customer_client.get(reverse("portal:new_request"))
    fields = set(response.context["form"].fields)

    assert "full_name" not in fields
    assert "email" not in fields
    assert {"category", "subject", "description"} <= fields


def test_the_address_cannot_be_supplied_by_the_caller(customer_client, category, contact):
    """The form has no email field, which is not the same as the view ignoring one.

    A view that read `request.POST["email"]` would let a signed-in customer raise a request
    against somebody else's contact record — and the screen would look exactly as it does now.
    """
    customer_client.post(
        reverse("portal:new_request"),
        {
            "category": category.pk,
            "subject": "Filed against somebody else",
            "description": "...",
            "email": contact.details.first().value,
            "full_name": "Sara Ahmed",
        },
    )

    ticket = Ticket.objects.get(subject="Filed against somebody else")
    assert ticket.contact != contact


def test_it_is_attached_to_their_contact(customer_client, customer_contact, category):
    """Scenario 2."""
    raise_request(customer_client, category)

    assert Ticket.objects.get(subject="A new problem").contact == customer_contact


def test_it_appears_in_their_list_at_once(customer_client, customer_contact, category):
    raise_request(customer_client, category)

    body = customer_client.get(reverse("portal:home")).content.decode()

    assert "A new problem" in body


def test_it_is_marked_as_coming_from_the_portal(customer_client, customer_contact, category):
    """Scenario 3's second half (FR-021)."""
    raise_request(customer_client, category)

    assert Ticket.objects.get(subject="A new problem").origin_channel == Ticket.Channel.PORTAL


def test_it_reaches_the_agent_queue(agent_client, customer_client, customer_contact, category):
    """Scenario 3. A request nobody works is not a request."""
    raise_request(customer_client, category)

    body = agent_client.get(reverse("tickets:queue")).content.decode()

    assert "A new problem" in body


def test_a_customer_with_no_contact_record_gets_one(customer_client, customer, category, branch):
    """T070. The ordinary case for a new account: registration deliberately creates no
    contact (research.md §2), so the first request is where the contact record begins.

    The name comes from the address, as the inbound email path already does for an unknown
    sender — asking a signed-in customer for their name on this form is exactly what FR-023
    forbids, and inventing a placeholder would put "Unknown" in the customer list.
    """
    assert not ContactDetail.objects.filter(value=customer.email).exists()

    raise_request(customer_client, category)

    detail = ContactDetail.objects.get(value=customer.email)
    assert Ticket.objects.get(subject="A new problem").contact == detail.contact
    assert detail.contact.full_name


def test_a_second_request_reuses_the_same_contact(customer_client, customer, category, branch):
    """Not a new contact record per request, which would fragment one person's history across
    the customer list and make the portal's own read query return only the newest."""
    raise_request(customer_client, category, subject="First")
    raise_request(customer_client, category, subject="Second")

    assert Contact.objects.filter(details__value=customer.email).distinct().count() == 1


def test_the_description_is_held_to_the_same_limit_as_a_reply(
    customer_client, customer_contact, category, settings
):
    """FR-024 is about customer-authored content, not about the reply screen."""
    settings.PORTAL_MESSAGE_MAX_LENGTH = 50

    response = raise_request(customer_client, category, description="x" * 51)

    assert not Ticket.objects.filter(subject="A new problem").exists()
    assert response.context["form"].errors.get("description")


def test_an_empty_subject_is_refused(customer_client, customer_contact, category):
    response = raise_request(customer_client, category, subject="   ")

    assert not Ticket.objects.exists()
    assert response.context["form"].errors.get("subject")


def test_an_unconfirmed_account_cannot_raise_one(client, customer, category):
    from django.conf import settings

    from apps.portal.auth import CUSTOMER_SESSION_KEY

    customer.email_confirmed_at = None
    customer.save(update_fields=["email_confirmed_at"])
    session = client.session
    session[CUSTOMER_SESSION_KEY] = customer.pk
    session.save()
    client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

    raise_request(client, category)

    assert not Ticket.objects.exists()


def test_the_empty_list_offers_the_portals_own_screen(customer_client):
    """US2 pointed this at the public form, which asks a signed-in customer for a name and an
    address the product already knows."""
    body = customer_client.get(reverse("portal:home")).content.decode()

    assert reverse("portal:new_request") in body
    assert reverse("intake:form") not in body


def test_a_new_contact_takes_the_customers_language(customer_client, customer, category, branch):
    """The account's language, not the request's.

    A customer reading the portal in Arabic is an Arabic speaker whichever language their
    browser happened to announce, and `preferred_language` is what every later reply from the
    desk is composed in.

    Worth its own test because dropping the assignment altogether broke nothing: the contact
    is created, the ticket is created, and only the emails weeks later are wrong.
    """
    customer.language = "ar"
    customer.save(update_fields=["language"])

    raise_request(customer_client, category)

    assert ContactDetail.objects.get(value=customer.email).contact.preferred_language == "ar"


def test_an_english_customer_gets_an_english_contact(customer_client, customer, category, branch):
    """So the rule cannot be satisfied by hard-coding Arabic, which is the default and would
    pass the test above."""
    customer.language = "en"
    customer.save(update_fields=["language"])

    raise_request(customer_client, category)

    assert ContactDetail.objects.get(value=customer.email).contact.preferred_language == "en"


def test_the_categories_are_offered_in_the_customers_language(
    customer_client, customer, department
):
    """MVP FR-031, on a screen built by spec 004.

    `Category.__str__` returns the English name, which is right for the admin and the audit
    log and wrong on a form a customer fills in: an Arabic customer was offered "Billing" and
    "Logistics" between labels reading الموضوع and ما الذي حدث؟.

    Found by opening the page. Nothing server-side could notice — every category renders, the
    form validates, the request is created.
    """
    from apps.tickets.models import Category

    Category.objects.create(name="Billing", name_ar="الفوترة", department=department)
    customer.language = "ar"
    customer.save(update_fields=["language"])

    body = customer_client.get(reverse("portal:new_request")).content.decode()

    assert "الفوترة" in body
    assert ">Billing<" not in body


def test_an_english_customer_is_offered_the_english_names(customer_client, customer, department):
    from apps.tickets.models import Category

    Category.objects.create(name="Billing", name_ar="الفوترة", department=department)
    customer.language = "en"
    customer.save(update_fields=["language"])

    body = customer_client.get(reverse("portal:new_request")).content.decode()

    assert ">Billing<" in body


def test_a_category_with_no_arabic_name_still_appears(customer_client, customer, department):
    """`name_ar` is blank-able. An untranslated category should read oddly, not vanish from
    the list — a customer who cannot choose it cannot raise that kind of request at all."""
    from apps.tickets.models import Category

    Category.objects.create(name="Untranslated", name_ar="", department=department)
    customer.language = "ar"
    customer.save(update_fields=["language"])

    assert ">Untranslated<" in customer_client.get(reverse("portal:new_request")).content.decode()
