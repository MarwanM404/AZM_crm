"""
Inbound mail transport adapters (FR-013, T145).

Threading is already decided and tested: `apps.messaging.services.inbound.ingest` takes one
message as a plain dict and applies the four rules in priority order. What is *not* decided is
how a message reaches it, because that depends on the mail domain, which IT controls
(ADR-006).

So transport is a seam with two implementations behind one interface:

- `WebhookAdapter` — a provider (Postmark, Mailgun, SendGrid) POSTs each inbound message to
  us. Preferred: no polling, so replies appear immediately, and the provider handles
  deliverability and bounce reporting.
- `ImapAdapter` — poll a mailbox on a schedule. Works with mail infrastructure that already
  exists and needs no new vendor, at the cost of a delay and of deliverability being the
  organization's own problem.

Both normalize to the same dict, so `ingest` neither knows nor cares which one is in use, and
switching is a settings change rather than a rewrite. See docs/email-setup.md for what to ask
IT for.
"""

import email
import imaplib
from email.header import decode_header, make_header

from django.conf import settings


def _decoded(value):
    """Mail headers arrive RFC 2047-encoded. Arabic subjects are the common case here and
    they arrive as base64 — decoding them wrongly is how a subject becomes mojibake."""
    if not value:
        return ""
    return str(make_header(decode_header(value)))


def _body_of(message):
    """The plain-text part. HTML-only mail falls back to the HTML, which the agent still sees
    as something rather than an empty message."""
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(part.get_content_charset() or "utf-8", "replace")
        for part in message.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(part.get_content_charset() or "utf-8", "replace")
        return ""
    payload = message.get_payload(decode=True)
    if payload is None:
        return message.get_payload() or ""
    return payload.decode(message.get_content_charset() or "utf-8", "replace")


def normalize_rfc822(raw_bytes):
    """One raw message to the dict `ingest` expects. Shared by both adapters, so a message
    threads identically however it arrived."""
    message = email.message_from_bytes(raw_bytes)
    return {
        "to": _decoded(message.get("To")),
        "from": email.utils.parseaddr(_decoded(message.get("From")))[1],
        "subject": _decoded(message.get("Subject")),
        "body": _body_of(message),
        "in_reply_to": (message.get("In-Reply-To") or "").strip(),
        "references": (message.get("References") or "").strip(),
        "message_id": (message.get("Message-ID") or "").strip(),
    }


class WebhookAdapter:
    """For a provider that POSTs inbound mail. The view that receives the POST calls
    `normalize_payload` then `ingest`; there is nothing to schedule."""

    @staticmethod
    def normalize_payload(payload):
        """Provider payload shapes differ; the fields we need do not. `RawEmail` is the
        full RFC822 message, which every major provider can send and which keeps us out of
        the business of trusting a provider's own parsing."""
        if raw := payload.get("RawEmail") or payload.get("raw") or payload.get("email"):
            if isinstance(raw, str):
                raw = raw.encode("utf-8", "replace")
            return normalize_rfc822(raw)

        return {
            "to": payload.get("To") or payload.get("recipient") or "",
            "from": payload.get("From") or payload.get("sender") or "",
            "subject": payload.get("Subject") or payload.get("subject") or "",
            "body": payload.get("TextBody")
            or payload.get("body-plain")
            or payload.get("text")
            or "",
            "in_reply_to": payload.get("In-Reply-To") or "",
            "references": payload.get("References") or "",
            "message_id": payload.get("MessageID") or payload.get("Message-Id") or "",
        }


class ImapAdapter:
    """For polling a real mailbox. Reads unseen messages, hands each to the caller, and marks
    them seen only after the caller has accepted them — so a crash mid-batch redelivers rather
    than silently losing mail."""

    def __init__(self, host=None, user=None, password=None, mailbox="INBOX", use_ssl=True):
        self.host = host or settings.INBOUND_EMAIL_HOST
        self.user = user or settings.INBOUND_EMAIL_USER
        self.password = password or settings.INBOUND_EMAIL_PASSWORD
        self.mailbox = mailbox
        self.use_ssl = use_ssl

    def fetch_unseen(self, limit=50):
        """Yields (uid, normalized_dict). The caller marks each seen with `mark_seen` once it
        has been stored."""
        connection = (imaplib.IMAP4_SSL if self.use_ssl else imaplib.IMAP4)(self.host)
        try:
            connection.login(self.user, self.password)
            connection.select(self.mailbox)
            _status, data = connection.search(None, "UNSEEN")
            uids = data[0].split()[:limit]
            for uid in uids:
                _status, parts = connection.fetch(uid, "(BODY.PEEK[])")  # PEEK: do not mark
                if parts and parts[0]:
                    yield uid.decode(), normalize_rfc822(parts[0][1])
        finally:
            try:
                connection.logout()
            except Exception:  # a failed logout must not lose the messages already yielded
                pass

    def mark_seen(self, uids):
        if not uids:
            return
        connection = (imaplib.IMAP4_SSL if self.use_ssl else imaplib.IMAP4)(self.host)
        try:
            connection.login(self.user, self.password)
            connection.select(self.mailbox)
            for uid in uids:
                connection.store(uid, "+FLAGS", "\\Seen")
        finally:
            try:
                connection.logout()
            except Exception:
                pass


def get_adapter():
    """Whichever transport settings name. Returns None when inbound mail is not configured,
    which is the current state (ADR-006) and must not be an error."""
    mode = getattr(settings, "INBOUND_EMAIL_MODE", "") or ""
    if mode == "webhook":
        return WebhookAdapter()
    if mode == "imap":
        return ImapAdapter()
    return None
