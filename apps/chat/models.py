"""
Conversation and Observation.

The durable half of live chat. Presence and the waiting queue live in Redis instead, because
they are *supposed* to be ephemeral — an agent whose server restarted is not online, and a
database row saying otherwise goes on saying it forever (research.md #3).
"""

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import ScopedSoftDeleteModel, TimeStampedModel


class Conversation(ScopedSoftDeleteModel):
    """One live chat session, always attached to a ticket."""

    class State(models.TextChoices):
        WAITING = "WAITING", _("Waiting")
        ACTIVE = "ACTIVE", _("Active")
        ENDED = "ENDED", _("Ended")

    class EndReason(models.TextChoices):
        RESOLVED = "RESOLVED", _("Resolved")
        ENDED_BY_AGENT = "ENDED_BY_AGENT", _("Ended by the agent")
        ENDED_BY_VISITOR = "ENDED_BY_VISITOR", _("Ended by the visitor")
        VISITOR_DISCONNECTED = "VISITOR_DISCONNECTED", _("The visitor disconnected")
        IDLE_TIMEOUT = "IDLE_TIMEOUT", _("Closed after inactivity")
        # FR-042: they were still waiting when the last agent went offline. Distinct
        # from every other ending because it is the only one that is the desk's fault,
        # and a supervisor reading these needs to see it as its own number.
        DESK_CLOSED = "DESK_CLOSED", _("The desk closed while waiting")

    #: Set when the conversation starts so a transcript can never be orphaned by an
    #: unexpected ending (FR-040). The agent may re-point it later, at which point the
    #: placeholder is soft-deleted (FR-041).
    ticket = models.ForeignKey(
        "tickets.Ticket", on_delete=models.PROTECT, related_name="conversations"
    )
    contact = models.ForeignKey(
        "customers.Contact", on_delete=models.PROTECT, related_name="conversations"
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="conversations",
    )

    state = models.CharField(max_length=10, choices=State.choices, default=State.WAITING)

    #: A HASH of the visitor's token, never the token. It is their only credential
    #: (research.md #5), and a readable column would make this table a list of live session
    #: keys — readable by anyone with database access, and retained as long as the row.
    visitor_token_hash = models.CharField(max_length=64, db_index=True)

    started_at = models.DateTimeField(default=timezone.now)
    assigned_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    ended_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    #: Recorded because "the customer left" and "the agent closed it" are different facts
    #: about the same ended conversation, and only one of them is a service problem.
    end_reason = models.CharField(max_length=25, choices=EndReason.choices, blank=True, default="")
    last_activity_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            # The queue and console both read "conversations in this scope in this state".
            models.Index(fields=["department", "branch", "state", "started_at"]),
        ]

    def __str__(self):
        return f"Conversation on {self.ticket.reference}"

    @property
    def is_open(self):
        return self.state in (self.State.WAITING, self.State.ACTIVE)


class Observation(TimeStampedModel):
    """A record that a supervisor watched a conversation.

    Deliberately NOT soft-deletable, unlike almost everything else here: an observation is a
    fact about something that happened, and there is no state in which it should be hidden.
    Watching a colleague's live conversation is an exercise of authority rather than a neutral
    read (FR-023), and agents are told these are logged.
    """

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="observations"
    )
    observer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="observations"
    )
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.observer} observed {self.conversation_id}"
