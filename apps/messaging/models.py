"""InboundMessageLog: raw inbound mail as received, retained so FR-013 threading failures are
diagnosable (which rule matched, or none) rather than mysterious."""

from django.db import models

from apps.core.models import TimeStampedModel
from apps.tickets.models import Ticket


class InboundMessageLog(TimeStampedModel):
    class MatchMethod(models.TextChoices):
        REPLY_TO_TOKEN = "REPLY_TO_TOKEN", "Reply-to token"
        HEADERS = "HEADERS", "In-Reply-To / References headers"
        SUBJECT_TOKEN = "SUBJECT_TOKEN", "Subject token"
        NONE = "NONE", "No match — new ticket created"

    received_at = models.DateTimeField(auto_now_add=True)
    raw_headers = models.JSONField(default=dict)
    matched_ticket = models.ForeignKey(
        Ticket, on_delete=models.SET_NULL, null=True, blank=True, related_name="inbound_logs"
    )
    match_method = models.CharField(max_length=20, choices=MatchMethod.choices)
    processing_error = models.TextField(blank=True)

    class Meta:
        ordering = ["-received_at"]
