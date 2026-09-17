"""
Outbound email sending (FR-016, contracts/email.md).

Queued rather than sent inline, with retry and backoff. A permanent failure is recorded on
the Message itself so it is visible to the agent on the ticket — never silently discarded.

A worker has no HTTP request, so django-auditlog cannot infer who caused a write. Every task
that writes to an audited record therefore takes the acting user explicitly and wraps its
work in `set_actor` (FR-027). Without that, the delivery-status write would be attributed to
nobody, and "who replied to this customer" stops being answerable.
"""

from auditlog.context import set_actor
from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import translation


def _portal_url(path_name):
    """An absolute link to the portal, for a message that will be read in a mail client.

    Absolute because a relative one is meaningless there — there is no page for it to be
    relative to. Built from `PORTAL_BASE_URL` rather than from the request, because by the time
    a worker runs this the request is gone, and a link built from a Host header is one an
    attacker can point wherever they like inside a message our own server sends.
    """
    from django.urls import reverse

    return f"{settings.PORTAL_BASE_URL.rstrip('/')}{reverse(path_name)}"


def _reply_to_address(reference):
    return f"support+{reference}@{settings.SUPPORT_EMAIL_DOMAIN}"


def _actor(actor_id):
    from apps.accounts.models import User

    return User.objects.filter(pk=actor_id).first() if actor_id else None


@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def send_confirmation_email(self, *, contact_id, ticket_reference, language):
    """FR-004: the intake confirmation. Its only write is the mail itself, so it carries no
    actor — the ticket it confirms was already audited by the request that created it."""
    from apps.customers.models import ContactDetail

    email = (
        ContactDetail.objects.filter(contact_id=contact_id, kind=ContactDetail.Kind.EMAIL)
        .values_list("value", flat=True)
        .first()
    )
    if not email:
        return

    with translation.override(language):
        subject = translation.gettext("Your request has been received: %(reference)s") % {
            "reference": ticket_reference
        }
        body = render_to_string(
            f"messaging/email/confirmation.{language}.txt",
            {
                "reference": ticket_reference,
                # The registration screen, deliberately — not the request itself. This message
                # is forwarded constantly, and a link that opened the ticket would be a way
                # into somebody's data from a colleague's inbox.
                "portal": _portal_url("portal:register"),
            },
        )

    try:
        EmailMultiAlternatives(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
            reply_to=[_reply_to_address(ticket_reference)],
        ).send(fail_silently=False)
    except Exception as exc:
        raise self.retry(exc=exc) from exc


@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def send_ticket_reply_email(self, *, message_id, actor_id=None):
    """Deliver a public outbound message to its ticket's contact.

    `actor_id` is the agent who sent the reply (FR-027). FR-015: this task refuses any
    message that is not PUBLIC, so it can never become the path by which an internal note
    reaches a customer.
    """
    with set_actor(_actor(actor_id)):
        return _deliver_reply(self, message_id)


def _deliver_reply(task, message_id):
    from apps.customers.models import ContactDetail
    from apps.tickets.models import Message

    try:
        message = Message.objects.select_related("ticket", "ticket__contact").get(pk=message_id)
    except Message.DoesNotExist:
        return

    if message.visibility != Message.Visibility.PUBLIC:
        # Defensive: never the path by which an internal message leaks (FR-015).
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

    from apps.messaging.services.outbound import language_for_contact

    language = language_for_contact(message.ticket.contact)
    with translation.override(language):
        subject = translation.gettext("Re: %(reference)s") % {"reference": message.ticket.reference}
        from apps.tickets.services.visibility import customer_facing_context

        # The context a customer-facing template may see is built in one place and cannot
        # contain an internal message (FR-015).
        body = render_to_string(
            f"messaging/email/reply.{language}.txt",
            customer_facing_context(
                message.ticket, body=message.body, portal=_portal_url("portal:sign_in")
            ),
        )

    try:
        EmailMultiAlternatives(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
            reply_to=[_reply_to_address(message.ticket.reference)],
        ).send(fail_silently=False)
    except Exception as exc:
        message.delivery_status = Message.DeliveryStatus.FAILED
        message.delivery_error = str(exc)
        message.save(update_fields=["delivery_status", "delivery_error"])
        raise task.retry(exc=exc) from exc
    else:
        message.delivery_status = Message.DeliveryStatus.SENT
        message.save(update_fields=["delivery_status"])


@shared_task
def collect_inbound_email():
    """
    Scheduled collection of inbound mail (Celery Beat, FR-013).

    Only used by the IMAP transport — a webhook needs no polling, since the provider posts to
    us. Messages are marked seen only after they have been stored, so a crash mid-batch
    redelivers rather than losing mail.
    """
    from apps.accounts.models import Branch, Department
    from apps.messaging.services.adapters import ImapAdapter, get_adapter
    from apps.messaging.services.inbound import ingest

    adapter = get_adapter()
    if adapter is None:
        return {"collected": 0, "reason": "inbound email is not configured (ADR-006)"}
    if not isinstance(adapter, ImapAdapter):
        return {"collected": 0, "reason": "webhook transport does not poll"}

    department = Department.objects.filter(is_active=True).order_by("pk").first()
    branch = Branch.objects.filter(is_active=True).order_by("pk").first()
    if department is None or branch is None:
        return {"collected": 0, "reason": "no active department or branch to file mail under"}

    stored = []
    for uid, message in adapter.fetch_unseen():
        log = ingest(message, department, branch)
        # Only mark seen once it is safely stored. A message retained with a processing error
        # still counts as stored — it is in the log and can be inspected, not lost.
        if log.pk:
            stored.append(uid)

    adapter.mark_seen(stored)
    return {"collected": len(stored)}
