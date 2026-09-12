"""
Inbound mail webhook (FR-013, T145).

Public by necessity — the provider is not a signed-in user — and therefore the one endpoint in
the system that accepts unauthenticated POSTs carrying content. Three things guard it:

1. A shared secret, compared in constant time, so a wrong guess leaks nothing through timing.
2. A size limit, so the endpoint cannot be used to fill the disk.
3. Everything it stores is treated as untrusted text. Inbound mail is written to the ticket
   thread and displayed to agents; it is never executed, never rendered unescaped, and the
   sender address is matched against existing contacts rather than trusted as identity.
"""

import hmac
import json
import logging

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)

MAX_PAYLOAD_BYTES = 25 * 1024 * 1024  # generous for attachments, bounded against abuse


@csrf_exempt  # the sender is a provider, not a browser session
@require_POST
def inbound_email_webhook(request):
    secret = settings.INBOUND_EMAIL_WEBHOOK_SECRET
    if not secret:
        # Refuse rather than accept anonymous mail: an unsecured endpoint would let anyone
        # inject messages onto any ticket.
        logger.error("Inbound webhook called but INBOUND_EMAIL_WEBHOOK_SECRET is unset")
        return HttpResponse(status=503)

    presented = request.headers.get("X-Webhook-Secret", "")
    if not hmac.compare_digest(presented, secret):
        logger.warning(
            "Inbound webhook rejected: bad secret from %s",
            request.META.get("REMOTE_ADDR", "unknown"),
        )
        return HttpResponse(status=403)

    if int(request.headers.get("Content-Length") or 0) > MAX_PAYLOAD_BYTES:
        return HttpResponse(status=413)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        logger.warning("Inbound webhook rejected: payload is not valid JSON")
        return HttpResponse(status=400)

    from apps.accounts.models import Branch, Department
    from apps.messaging.services.adapters import WebhookAdapter
    from apps.messaging.services.inbound import ingest

    department = Department.objects.filter(is_active=True).order_by("pk").first()
    branch = Branch.objects.filter(is_active=True).order_by("pk").first()
    if department is None or branch is None:
        logger.error("Inbound mail arrived with no active department or branch to file it under")
        return HttpResponse(status=503)

    message = WebhookAdapter.normalize_payload(payload)
    log = ingest(message, department, branch)

    # 200 even when the message could not be threaded: it is stored in InboundMessageLog with
    # its error, and telling the provider to retry would duplicate it rather than fix it.
    return JsonResponse(
        {
            "stored": bool(log.pk),
            "matched": bool(log.matched_ticket_id),
            "match_method": log.match_method,
        }
    )
