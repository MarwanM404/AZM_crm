"""
FR-013 and contracts/email.md: the four threading rules, in priority order.

Each rule is tested in isolation AND the priority between them is tested, because the whole
point of the ordering is that a more reliable signal wins when two disagree.
"""

import pytest

from apps.messaging.models import InboundMessageLog
from apps.messaging.services.inbound import ingest
from apps.tickets.models import Message, Ticket


def mail(
    to="support@example.com",
    sender="sara@najd-trading.example",
    subject="Re: help",
    body="Any update?",
    in_reply_to="",
    references="",
):
    return {
        "to": to,
        "from": sender,
        "subject": subject,
        "body": body,
        "in_reply_to": in_reply_to,
        "references": references,
    }


@pytest.mark.django_db
def test_rule_1_reply_to_token_matches(ticket, department, branch):
    ingest(mail(to=f"support+{ticket.reference}@example.com"), department, branch)

    log = InboundMessageLog.objects.get()
    assert log.matched_ticket == ticket
    assert log.match_method == InboundMessageLog.MatchMethod.REPLY_TO_TOKEN
    assert ticket.messages.count() == 1


@pytest.mark.django_db
def test_rule_2_headers_match_a_known_outbound_message(ticket, agent, department, branch):
    outbound = Message.objects.create(
        ticket=ticket,
        author=agent,
        direction=Message.Direction.OUTBOUND,
        visibility=Message.Visibility.PUBLIC,
        channel=Ticket.Channel.EMAIL,
        body="Our reply",
        external_id="<msg-abc@example.com>",
    )
    ingest(mail(in_reply_to=outbound.external_id), department, branch)

    log = InboundMessageLog.objects.get()
    assert log.matched_ticket == ticket
    assert log.match_method == InboundMessageLog.MatchMethod.HEADERS


@pytest.mark.django_db
def test_rule_3_subject_token_matches(ticket, department, branch):
    ingest(mail(subject=f"Re: {ticket.reference} still broken"), department, branch)

    log = InboundMessageLog.objects.get()
    assert log.matched_ticket == ticket
    assert log.match_method == InboundMessageLog.MatchMethod.SUBJECT_TOKEN


@pytest.mark.django_db
def test_rule_4_no_match_creates_a_new_ticket(department, branch, category):
    ingest(mail(subject="Brand new problem", sender="newcomer@example.com"), department, branch)

    log = InboundMessageLog.objects.get()
    assert log.match_method == InboundMessageLog.MatchMethod.NONE
    assert log.matched_ticket is not None
    assert log.matched_ticket.subject == "Brand new problem"
    assert log.matched_ticket.origin_channel == Ticket.Channel.EMAIL


@pytest.mark.django_db
def test_reply_to_token_beats_a_conflicting_subject_token(
    ticket, department, branch, category, contact
):
    decoy = Ticket.objects.create(
        contact=contact,
        subject="Decoy",
        description="...",
        category=category,
        origin_channel=Ticket.Channel.WEB_FORM,
        department=department,
        branch=branch,
    )
    # Addressed to `ticket`, but quoting `decoy`'s reference in the subject.
    ingest(
        mail(to=f"support+{ticket.reference}@example.com", subject=f"Re: {decoy.reference}"),
        department,
        branch,
    )

    log = InboundMessageLog.objects.get()
    assert log.matched_ticket == ticket  # the more reliable signal wins


@pytest.mark.django_db
def test_unknown_sender_creates_a_contact_with_no_organization(department, branch, category):
    ingest(mail(sender="stranger@elsewhere.example"), department, branch)

    ticket = InboundMessageLog.objects.get().matched_ticket
    assert ticket.contact.organization is None  # FR-040


@pytest.mark.django_db
def test_inbound_message_is_public_and_inbound(ticket, department, branch):
    ingest(mail(to=f"support+{ticket.reference}@example.com"), department, branch)

    message = ticket.messages.get()
    assert message.direction == Message.Direction.INBOUND
    assert message.visibility == Message.Visibility.PUBLIC
    assert message.author is None  # written by the customer, not a staff member


@pytest.mark.django_db
def test_arabic_subject_and_body_survive_ingestion(ticket, department, branch):
    ingest(
        mail(
            to=f"support+{ticket.reference}@example.com",
            subject="لا يزال الشحن مفقودًا",
            body="لم يصل شيء حتى الآن.",
        ),
        department,
        branch,
    )
    assert ticket.messages.get().body == "لم يصل شيء حتى الآن."


@pytest.mark.django_db
def test_unprocessable_mail_is_retained_with_its_error(department, branch):
    ingest({"to": "support@example.com"}, department, branch)  # malformed: no sender

    log = InboundMessageLog.objects.get()
    assert log.processing_error
    assert log.matched_ticket is None
