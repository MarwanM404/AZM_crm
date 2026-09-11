"""
FR-015, contracts/email.md: quoted history in outbound email carries public messages only.

The MVP's reply template does not quote history at all, so today this holds trivially. These
tests are written anyway, because quoting is the single most likely future addition to a
support email and the one most likely to leak: whoever adds it will reach for the thread, and
`ticket.messages.all()` is one filter away from `public_messages_for(ticket)`.

The guard is structural rather than hopeful — the template is rendered with a context that
cannot reach an internal message — so these tests keep passing when quoting is added
correctly, and fail the moment it is added the easy way.
"""

import pytest
from django.template.loader import render_to_string

from apps.tickets.models import Message
from apps.tickets.services.visibility import customer_facing_context

INTERNAL = "INTERNAL-ONLY-CARRIER-DISPUTE-NOTE"
PUBLIC = "We have opened an investigation with the carrier."


@pytest.fixture
def threaded_ticket(ticket, agent):
    for visibility, body in (
        (Message.Visibility.PUBLIC, PUBLIC),
        (Message.Visibility.INTERNAL, INTERNAL),
    ):
        Message.objects.create(
            ticket=ticket,
            author=agent,
            direction=Message.Direction.OUTBOUND,
            visibility=visibility,
            channel=ticket.origin_channel,
            body=body,
        )
    return ticket


@pytest.mark.django_db
@pytest.mark.parametrize("language", ["en", "ar"])
def test_reply_template_renders_no_internal_content(threaded_ticket, language):
    rendered = render_to_string(
        f"messaging/email/reply.{language}.txt",
        customer_facing_context(threaded_ticket, body="Latest update."),
    )
    assert INTERNAL not in rendered


@pytest.mark.django_db
def test_the_history_available_to_a_template_is_public_only(threaded_ticket):
    """If a template quotes `public_messages`, this is everything it can quote."""
    context = customer_facing_context(threaded_ticket)
    quotable = [m.body for m in context["public_messages"]]

    assert PUBLIC in quotable
    assert INTERNAL not in quotable


@pytest.mark.django_db
def test_a_template_that_quotes_history_stays_safe(threaded_ticket):
    """Prove the guarantee rather than assume it: render a template that DOES quote the
    thread, using the real customer-facing context, and confirm it cannot reach the note."""
    from django.template import Context, Template

    quoting = Template(
        "{{ body }}\n\n--- Previous messages ---\n"
        "{% for message in public_messages %}> {{ message.body }}\n{% endfor %}"
    )
    rendered = quoting.render(
        Context(customer_facing_context(threaded_ticket, body="Latest update."))
    )

    assert PUBLIC in rendered  # quoting works
    assert INTERNAL not in rendered  # and still cannot reach the note


@pytest.mark.django_db
def test_the_unsafe_version_of_that_template_would_leak(threaded_ticket):
    """The counterpart, showing what the guarantee is worth. Handed the ticket itself — the
    obvious thing to pass — the same template reaches straight past the filter."""
    from django.template import Context, Template

    quoting = Template("{% for message in ticket.messages.all %}> {{ message.body }}\n{% endfor %}")
    rendered = quoting.render(Context({"ticket": threaded_ticket}))

    assert INTERNAL in rendered, (
        "This test documents the failure mode; if it stops leaking, the filter moved and "
        "this test should be revisited rather than deleted."
    )
