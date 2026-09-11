"""
Outbound email sending (FR-016, contracts/email.md).

Queued rather than sent inline, with retry and backoff. A permanent failure is recorded on
the Message itself so it is visible to the agent on the ticket — never silently discarded.
"""

from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import translation


@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def send_confirmation_email(self, *, contact_id, ticket_reference, language):
    from apps.customers.models import ContactDetail

    email = (
        ContactDetail.objects.filter(contact_id=contact_id, kind=ContactDetail.Kind.EMAIL)
        .values_list("value", flat=True)
        .first()
    )
    if not email:
        return  # nothing to send to; nothing queued elsewhere depends on this task's result

    with translation.override(language):
        subject = translation.gettext("Your request has been received: %(reference)s") % {
            "reference": ticket_reference
        }
        body = render_to_string(
            f"messaging/email/confirmation.{language}.txt", {"reference": ticket_reference}
        )

    from django.conf import settings

    reply_to = f"support+{ticket_reference}@{settings.SUPPORT_EMAIL_DOMAIN}"
    try:
        message = EmailMultiAlternatives(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
            reply_to=[reply_to],
        )
        message.send(fail_silently=False)
    except Exception as exc:
        raise self.retry(exc=exc) from exc


@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def send_ticket_reply_email(self, *, message_id):
    """Sends a Message(direction=OUTBOUND, visibility=PUBLIC) to its ticket's contact.
    FR-015: only ever called for public messages — see apps/tickets/views.py."""
    from django.conf import settings

    from apps.customers.models import ContactDetail
    from apps.tickets.models import Message

    try:
        message = Message.objects.select_related("ticket", "ticket__contact").get(pk=message_id)
    except Message.DoesNotExist:
        return

    if message.visibility != Message.Visibility.PUBLIC:
        # Defensive: this task must never be the path by which an internal message leaks.
        return

    email = (
        ContactDetail.objects.filter(contact=message.ticket.contact, kind=ContactDetail.Kind.EMAIL)
        .values_list("value", flat=True)
        .first()
    )
    if not email:
        message.delivery_status = Message.DeliveryStatus.FAILED
        message.delivery_error = "Contact has no email address on file."
        message.save(update_fields=["delivery_status", "delivery_error"])
        return

    language = message.ticket.contact.preferred_language
    with translation.override(language):
        subject = translation.gettext("Re: %(reference)s") % {"reference": message.ticket.reference}
        body = render_to_string(
            f"messaging/email/reply.{language}.txt",
            {"reference": message.ticket.reference, "body": message.body},
        )

    reply_to = f"support+{message.ticket.reference}@{settings.SUPPORT_EMAIL_DOMAIN}"
    try:
        email_message = EmailMultiAlternatives(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
            reply_to=[reply_to],
        )
        email_message.send(fail_silently=False)
    except Exception as exc:
        message.delivery_status = Message.DeliveryStatus.FAILED
        message.delivery_error = str(exc)
        message.save(update_fields=["delivery_status", "delivery_error"])
        raise self.retry(exc=exc) from exc
    else:
        message.delivery_status = Message.DeliveryStatus.SENT
        message.save(update_fields=["delivery_status"])


@shared_task
def collect_inbound_email():
    """
    Scheduled collection of inbound mail (Celery Beat).

    The adapter behind this is decided with the deployment target (ADR-006): a provider
    webhook where one exists, otherwise IMAP polling. Until that is settled, this task is the
    seam — `apps.messaging.services.inbound.ingest` is what either adapter calls, and it is
    fully tested independently of how the mail arrives.
    """
    from django.conf import settings

    if not getattr(settings, "INBOUND_EMAIL_ENABLED", False):
        return {"collected": 0, "reason": "inbound collection not configured (ADR-006)"}

    raise NotImplementedError(
        "Inbound mail adapter is pending the deployment decision in ADR-006 (T145)."
    )
