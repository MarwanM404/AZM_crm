"""
Opening a ticket on behalf of somebody outside the organization (T073).

Extracted from `apps.intake.views.request_form`, where it was inline, so that the public form
and the customer portal run the same code rather than two implementations that agree today.

FR-025 requires the anonymous form to keep working exactly as it does. Sharing the path is how
that is obtained: the public form cannot drift without the portal drifting with it, and
`apps/intake/tests/test_public_form_is_unchanged.py` pins the public behaviour on its own
terms, without mentioning the portal at all.

What is deliberately NOT here: the honeypot and the minimum-completion-time check. Those are
abuse protections for an anonymous public form and belong on that form. A signed-in customer
has already proved an address, and making them wait three seconds before submitting would be
protecting against a threat that registration and confirmation already handled.
"""

from django.db import transaction

from apps.accounts.services.defaults import default_branch
from apps.customers.services.matching import find_or_create_contact
from apps.tickets.models import Ticket


@transaction.atomic
def open_ticket(*, full_name, email, subject, description, category, channel, language):
    """Create the contact if needed and the ticket, and return `(ticket, contact, created)`.

    One transaction, so a partial failure never leaves an orphaned contact with no ticket —
    which would put somebody in the customer list who has never actually contacted the desk.

    `department` comes from the category and `branch` from the configured default, exactly as
    the public form has always done. Neither is a portal decision: a customer has no
    department and must never acquire one (FR-028), so the ticket's scope is derived from what
    they asked about rather than from who they are.
    """
    branch = default_branch()
    department = category.department

    contact, created = find_or_create_contact(
        full_name=full_name, email=email, department=department, branch=branch
    )
    if created:
        contact.preferred_language = language
        contact.save(update_fields=["preferred_language"])

    ticket = Ticket.objects.create(
        contact=contact,
        organization=contact.organization,
        subject=subject,
        description=description,
        category=category,
        origin_channel=channel,
        department=department,
        branch=branch,
    )
    return ticket, contact, created
