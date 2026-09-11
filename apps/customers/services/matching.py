"""
Contact matching for intake (FR-002, SC-003).

Email is normalized to lower case before lookup so `Jane@Example.com` and
`jane@example.com` match the same contact rather than creating a duplicate.
"""

from apps.customers.models import Contact, ContactDetail


def find_or_create_contact(*, full_name: str, email: str, department, branch):
    """Returns (contact, created). A matched contact's name is NOT overwritten (edge case:
    two submissions with the same email but different names must not silently rewrite the
    stored name)."""
    normalized_email = email.strip().lower()
    existing_detail = (
        ContactDetail.objects.filter(kind=ContactDetail.Kind.EMAIL, value=normalized_email)
        .select_related("contact")
        .first()
    )
    if existing_detail:
        return existing_detail.contact, False

    contact = Contact.objects.create(
        full_name=full_name,
        organization=None,  # FR-040: unknown employer until staff link it
        department=department,
        branch=branch,
    )
    ContactDetail.objects.create(
        contact=contact,
        kind=ContactDetail.Kind.EMAIL,
        value=normalized_email,
        is_primary=True,
        department=department,
        branch=branch,
    )
    return contact, True
