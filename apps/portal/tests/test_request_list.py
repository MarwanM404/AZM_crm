"""
T042-T045. The list of a customer's own requests (FR-013, FR-014, FR-018).

"Their own" means the requests raised from the address they confirmed — not their
organization's, not their colleagues', and not anything the account was linked to at
registration, because it is linked to nothing. research.md §2 settles why the match happens at
read time: a customer who registers before writing in gets an empty list rather than a broken
one, an administrator editing a contact's address does not silently move what the customer can
see, and an address recorded on two contacts matches both.

The organization test is the one to keep. Every other assertion here would still pass if the
query filtered by organization instead of by address — and filtering by organization is the
natural thing to write, because `Ticket` has an `organization` field sitting right there.
"""

import pytest
from django.urls import reverse

from apps.tickets.models import Ticket

pytestmark = pytest.mark.django_db


def test_the_list_shows_their_request(customer_client, customer_ticket):
    body = customer_client.get(reverse("portal:home")).content.decode()

    assert customer_ticket.reference in body
    assert customer_ticket.subject in body


def test_it_shows_status_and_both_dates(customer_client, customer_ticket):
    """FR-014. Dates plural: when it was opened and when it last moved.

    The second is the one a customer actually reads — "opened three weeks ago" without "last
    changed yesterday" is the information that makes somebody write in to ask whether anyone
    is looking at it, which is the message this portal exists to prevent.
    """
    # English, because the assertion below names an English label. The account defaults to
    # Arabic, and `get_status_display()` evaluated here returns whatever language the TEST is
    # running in — so this passed or failed on the ambient locale rather than on the page.
    customer_client.post(reverse("portal:language"), {"language": "en"})

    response = customer_client.get(reverse("portal:home"))
    body = response.content.decode()

    assert str(customer_ticket.get_status_display()) in body
    rows = response.context["requests"]
    assert list(rows) == [customer_ticket]
    assert rows[0].created_at and rows[0].updated_at


def test_a_customer_with_no_history_sees_an_invitation(customer_client):
    """T043, scenario 2. A customer exists before their first ticket does, so this is the
    ordinary state of a new account and not an edge case.

    An error here, or an empty page with nothing on it, is how somebody concludes the portal
    is broken minutes after being told to use it.
    """
    response = customer_client.get(reverse("portal:home"))

    assert response.status_code == 200
    assert list(response.context["requests"]) == []
    # The portal's own screen since User Story 4. It pointed at the public request form
    # first, which asks a signed-in customer for a name and an address the product already
    # knows — a way forward, but a worse one.
    assert reverse("portal:new_request") in response.content.decode()


def test_a_colleague_at_the_same_organization_is_not_shown(
    customer_client, customer_contact, category, department, branch
):
    """T044, FR-018, scenario 6. The test this file exists for.

    The portal shows the requests of an ADDRESS, not of a company. Filtering by organization
    would pass every other test here and would show a junior employee every complaint their
    colleagues have ever made — including, at an organization of one, nothing different at
    all, which is why this needs a colleague to be visible.
    """
    from apps.customers.models import Organization
    from apps.customers.services.matching import find_or_create_contact

    organization = Organization.objects.create(
        name="Najd Trading", department=department, branch=branch
    )
    customer_contact.organization = organization
    customer_contact.save(update_fields=["organization"])

    colleague, _ = find_or_create_contact(
        full_name="Faisal Someone",
        email="faisal@najd.example",
        department=department,
        branch=branch,
    )
    colleague.organization = organization
    colleague.save(update_fields=["organization"])
    theirs = Ticket.objects.create(
        contact=colleague,
        organization=organization,
        subject="A colleague's private complaint",
        description="...",
        category=category,
        origin_channel=Ticket.Channel.EMAIL,
        department=department,
        branch=branch,
    )

    body = customer_client.get(reverse("portal:home")).content.decode()

    assert theirs.reference not in body
    assert "A colleague's private complaint" not in body


def test_one_address_cannot_be_recorded_on_two_live_contacts(
    customer, customer_contact, department, branch
):
    """T045, and a correction to research.md §2.

    That section claims an address recorded on two contacts matches both and the customer
    sees both histories. The database does not allow it: ContactDetail carries a unique
    constraint on (kind, value) for rows that are not soft-deleted, so the second record
    cannot exist. The claim was written from the portal's side without checking the schema.

    What IS possible is a superseded detail — soft-deleted, so outside the constraint — and
    the test below covers that. The read query still uses `contact_id__in` rather than a
    single lookup, which costs nothing and is correct if the constraint is ever relaxed.
    """
    from django.db.utils import IntegrityError

    from apps.customers.models import Contact, ContactDetail

    duplicate = Contact.objects.create(
        full_name="N. Al-Harbi", department=department, branch=branch
    )

    with pytest.raises(IntegrityError):
        ContactDetail.objects.create(
            contact=duplicate,
            kind=ContactDetail.Kind.EMAIL,
            value=customer.email,
            department=department,
            branch=branch,
        )


def test_a_superseded_contact_detail_stops_matching(
    customer_client,
    customer,
    customer_contact,
    customer_ticket,
    category,
    department,
    branch,
    agent,
):
    """The case that actually arises: a detail is removed and the address re-recorded
    elsewhere. Only the live record matches, which is the same answer staff see."""
    from apps.customers.models import Contact, ContactDetail

    old_detail = ContactDetail.objects.get(contact=customer_contact, kind=ContactDetail.Kind.EMAIL)
    old_detail.soft_delete(by=agent)

    replacement = Contact.objects.create(
        full_name="Noura Al-Harbi", department=department, branch=branch
    )
    ContactDetail.objects.create(
        contact=replacement,
        kind=ContactDetail.Kind.EMAIL,
        value=customer.email,
        department=department,
        branch=branch,
    )
    moved = Ticket.objects.create(
        contact=replacement,
        subject="Raised after the address moved",
        description="...",
        category=category,
        origin_channel=Ticket.Channel.EMAIL,
        department=department,
        branch=branch,
    )

    body = customer_client.get(reverse("portal:home")).content.decode()

    assert moved.reference in body
    assert customer_ticket.reference not in body


def test_the_list_follows_the_address_not_a_stored_link(
    customer_client, customer, customer_contact, customer_ticket
):
    """research.md §2, asserted rather than trusted.

    An administrator corrects a contact's address. The customer proved one address and only
    that one, so their view follows it — and the tickets of the record that moved away stop
    being theirs. A stored link made at registration would keep showing them.
    """
    from apps.customers.models import ContactDetail

    detail = ContactDetail.objects.get(contact=customer_contact, kind=ContactDetail.Kind.EMAIL)
    detail.value = "someone.else@example.com"
    detail.save(update_fields=["value"])

    body = customer_client.get(reverse("portal:home")).content.decode()

    assert customer_ticket.reference not in body


def test_a_soft_deleted_request_is_not_listed(customer_client, customer_ticket, agent):
    """Soft deletion is this product's delete (MVP FR-020). A record staff have deleted must
    not keep being served to the customer through a door staff do not look at."""
    customer_ticket.soft_delete(by=agent)

    body = customer_client.get(reverse("portal:home")).content.decode()

    assert customer_ticket.reference not in body


def test_resolved_and_closed_requests_stay_listed(customer_client, customer_ticket):
    """FR-019. A customer looking up what was agreed six weeks ago is the second most common
    reason to open this page."""
    customer_ticket.status = Ticket.Status.CLOSED
    customer_ticket.save(update_fields=["status"])

    assert customer_ticket.reference in customer_client.get(reverse("portal:home")).content.decode()


def test_the_list_is_newest_first(
    customer_client, customer_contact, customer_ticket, category, department, branch
):
    """Whatever order is chosen it must be a chosen one. An unordered queryset is ordered by
    whatever the database finds convenient, which changes under load and looks like a bug."""
    newer = Ticket.objects.create(
        contact=customer_contact,
        subject="Something that happened today",
        description="...",
        category=category,
        origin_channel=Ticket.Channel.EMAIL,
        department=department,
        branch=branch,
    )

    rows = customer_client.get(reverse("portal:home")).context["requests"]

    assert list(rows) == [newer, customer_ticket]
