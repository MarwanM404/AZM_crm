"""
Category, Ticket, Message.

Ticket keeps its own `organization` reference rather than reading through `contact.organization`
(FR-042): if a contact is later moved to a different organization, tickets already raised keep
the organization they were actually raised under.
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import ScopedSoftDeleteModel, TimeStampedModel


class Category(TimeStampedModel):
    """Administrator-maintained (FR-007). Carries the department a ticket in this category
    routes to, since the public intake form does not ask a visitor for one directly."""

    name = models.CharField(_("name"), max_length=100)
    name_ar = models.CharField(_("name (Arabic)"), max_length=100, blank=True)
    department = models.ForeignKey(
        "accounts.Department", on_delete=models.PROTECT, related_name="categories"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Ticket(ScopedSoftDeleteModel):
    class Priority(models.TextChoices):
        LOW = "LOW", _("Low")
        NORMAL = "NORMAL", _("Normal")
        HIGH = "HIGH", _("High")
        URGENT = "URGENT", _("Urgent")

    class Status(models.TextChoices):
        NEW = "NEW", _("New")
        OPEN = "OPEN", _("Open")
        PENDING_CUSTOMER = "PENDING_CUSTOMER", _("Pending customer")
        RESOLVED = "RESOLVED", _("Resolved")
        CLOSED = "CLOSED", _("Closed")

    class Channel(models.TextChoices):
        WEB_FORM = "WEB_FORM", _("Web form")
        EMAIL = "EMAIL", _("Email")

    # Confirmed with stakeholders 2026-09-12 (T147). Changing these now means migrating
    # live ticket data, so treat an edit here as a schema change, not a tweak.
    ALLOWED_TRANSITIONS = {
        Status.NEW: {Status.OPEN, Status.RESOLVED},
        Status.OPEN: {Status.PENDING_CUSTOMER, Status.RESOLVED},
        Status.PENDING_CUSTOMER: {Status.OPEN, Status.RESOLVED},
        Status.RESOLVED: {Status.OPEN, Status.CLOSED},
        Status.CLOSED: {Status.OPEN},
    }

    reference = models.CharField(max_length=30, unique=True, editable=False)
    organization = models.ForeignKey(
        "customers.Organization",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="tickets",
    )
    contact = models.ForeignKey(
        "customers.Contact", on_delete=models.PROTECT, related_name="tickets"
    )
    subject = models.CharField(max_length=255)
    description = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="tickets")
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.NORMAL)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tickets",
    )
    origin_channel = models.CharField(max_length=10, choices=Channel.choices)
    first_response_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["department", "branch", "status", "priority", "created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["reference"],
                condition=models.Q(deleted_at__isnull=True),
                name="unique_ticket_reference_when_not_deleted",
            )
        ]

    def __str__(self):
        return self.reference

    def save(self, *args, **kwargs):
        if not self.reference:
            from apps.tickets.services.reference import next_ticket_reference

            self.reference = next_ticket_reference()
        super().save(*args, **kwargs)

    def can_transition_to(self, new_status: str) -> bool:
        return new_status in self.ALLOWED_TRANSITIONS.get(self.status, set())  # type: ignore[call-overload]


class Message(TimeStampedModel):
    class Direction(models.TextChoices):
        INBOUND = "INBOUND", _("Inbound")
        OUTBOUND = "OUTBOUND", _("Outbound")

    class Visibility(models.TextChoices):
        PUBLIC = "PUBLIC", _("Public")
        INTERNAL = "INTERNAL", _("Internal")

    class DeliveryStatus(models.TextChoices):
        PENDING = "PENDING", _("Pending")
        SENT = "SENT", _("Sent")
        FAILED = "FAILED", _("Failed")
        NOT_APPLICABLE = "NOT_APPLICABLE", _("Not applicable")

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="messages")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    direction = models.CharField(max_length=10, choices=Direction.choices)
    # FR-014, FR-015: this is the boundary every customer-facing output filters on.
    # See apps/tickets/services/visibility.py — never inline this filter elsewhere.
    visibility = models.CharField(max_length=10, choices=Visibility.choices)
    channel = models.CharField(max_length=10, choices=Ticket.Channel.choices)
    body = models.TextField()
    delivery_status = models.CharField(
        max_length=15, choices=DeliveryStatus.choices, default=DeliveryStatus.NOT_APPLICABLE
    )
    delivery_error = models.TextField(blank=True)
    external_id = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.ticket.reference}: {self.visibility} {self.direction}"
