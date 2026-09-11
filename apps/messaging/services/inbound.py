"""
Inbound email ingestion and threading (FR-013, contracts/email.md).

Four rules, applied in priority order, because a more reliable signal must win when two
disagree:

1. Reply-to token  — `support+<reference>@domain`. Survives clients that rewrite subjects
                     and strip threading headers, so it is tried first.
2. Headers         — In-Reply-To / References matching a known outbound message id.
3. Subject token   — a reference quoted in the subject. Last resort: customers edit subjects,
                     and a quoted reference can belong to an unrelated ticket.
4. No match        — create a new ticket rather than dropping the mail.

Whichever rule matched is recorded on InboundMessageLog.match_method, so a misthreaded mail
is diagnosable instead of mysterious.
"""

import logging
import re

from django.db import transaction

from apps.messaging.models import InboundMessageLog
from apps.tickets.models import Message, Ticket
from apps.tickets.services.lifecycle import reopen_for_customer_reply

logger = logging.getLogger(__name__)

REFERENCE_RE = re.compile(r"\b(AZM-\d{4}-\d{6})\b")
PLUS_ADDRESS_RE = re.compile(r"\+(AZM-\d{4}-\d{6})@")


def _by_reply_to_token(mail):
    match = PLUS_ADDRESS_RE.search(mail.get("to", "") or "")
    if not match:
        return None, None
    ticket = Ticket.objects.filter(reference=match.group(1)).first()
    return (ticket, InboundMessageLog.MatchMethod.REPLY_TO_TOKEN) if ticket else (None, None)


def _by_headers(mail):
    ids = []
    for key in ("in_reply_to", "references"):
        value = (mail.get(key) or "").strip()
        if value:
            ids.extend(value.split())
    if not ids:
        return None, None
    message = Message.objects.filter(external_id__in=ids).select_related("ticket").first()
    return (message.ticket, InboundMessageLog.MatchMethod.HEADERS) if message else (None, None)


def _by_subject_token(mail):
    match = REFERENCE_RE.search(mail.get("subject", "") or "")
    if not match:
        return None, None
    ticket = Ticket.objects.filter(reference=match.group(1)).first()
    return (ticket, InboundMessageLog.MatchMethod.SUBJECT_TOKEN) if ticket else (None, None)


def _default_category(department):
    from apps.tickets.models import Category

    category = Category.objects.filter(department=department, is_active=True).first()
    if category is None:
        category = Category.objects.create(name="General", department=department)
    return category


def ingest(mail, department, branch):
    """Store one inbound mail. Never raises for bad input: an unprocessable message is
    retained with its error so it can be inspected, never silently dropped."""
    log = InboundMessageLog(
        raw_headers={k: v for k, v in mail.items() if k != "body"},
        match_method=InboundMessageLog.MatchMethod.NONE,
    )

    sender = (mail.get("from") or "").strip()
    if not sender:
        log.processing_error = "Inbound mail has no sender address; cannot attribute it."
        log.save()
        logger.warning("Inbound mail rejected: no sender")
        return log

    try:
        with transaction.atomic():
            ticket = method = None
            for rule in (_by_reply_to_token, _by_headers, _by_subject_token):
                ticket, method = rule(mail)
                if ticket:
                    break

            if ticket is None:
                ticket = _new_ticket(mail, sender, department, branch)
                method = InboundMessageLog.MatchMethod.NONE
            else:
                reopen_for_customer_reply(ticket)

            Message.objects.create(
                ticket=ticket,
                author=None,  # written by the customer, not a staff member
                direction=Message.Direction.INBOUND,
                visibility=Message.Visibility.PUBLIC,
                channel=Ticket.Channel.EMAIL,
                body=mail.get("body", ""),
                delivery_status=Message.DeliveryStatus.NOT_APPLICABLE,
            )

            log.matched_ticket = ticket
            log.match_method = method
            log.save()
    except Exception as exc:  # retained, never dropped
        logger.exception("Inbound mail could not be processed")
        log.matched_ticket = None
        log.processing_error = str(exc)
        log.save()
    return log


def _new_ticket(mail, sender, department, branch):
    from apps.customers.services.matching import find_or_create_contact

    contact, _created = find_or_create_contact(
        full_name=sender.split("@")[0], email=sender, department=department, branch=branch
    )
    subject = (mail.get("subject") or "").strip() or "(no subject)"
    return Ticket.objects.create(
        contact=contact,
        organization=contact.organization,
        subject=subject[:255],
        description=mail.get("body", ""),
        category=_default_category(department),
        origin_channel=Ticket.Channel.EMAIL,
        department=department,
        branch=branch,
    )
