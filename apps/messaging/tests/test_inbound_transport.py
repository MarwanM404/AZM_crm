"""
T145: the transport in front of `ingest` — the webhook endpoint and the RFC822 normalizer.

Threading itself is covered by test_inbound_threading.py. These cover the layer that was
missing: how a message gets here, and whether an unauthenticated public endpoint can be
abused.
"""

import json

import pytest
from django.urls import reverse

from apps.messaging.models import InboundMessageLog
from apps.messaging.services.adapters import WebhookAdapter, normalize_rfc822

WEBHOOK = "messaging:inbound_webhook"
SECRET = "a-shared-secret-for-tests"


@pytest.fixture
def configured(settings):
    settings.INBOUND_EMAIL_WEBHOOK_SECRET = SECRET
    return settings


def _post(client, payload, secret=SECRET):
    return client.post(
        reverse(WEBHOOK),
        data=json.dumps(payload),
        content_type="application/json",
        headers={"x-webhook-secret": secret},
    )


# --- the endpoint's guards ---


@pytest.mark.django_db
def test_a_wrong_secret_is_refused(configured, client, department, branch):
    response = _post(client, {"From": "a@b.example"}, secret="not-the-secret")
    assert response.status_code == 403
    assert not InboundMessageLog.objects.exists()


@pytest.mark.django_db
def test_a_missing_secret_is_refused(configured, client, department, branch):
    response = client.post(reverse(WEBHOOK), data="{}", content_type="application/json")
    assert response.status_code == 403


@pytest.mark.django_db
def test_the_endpoint_refuses_to_run_unconfigured(settings, client, department, branch):
    """An unset secret must fail closed. Accepting anonymous mail would let anyone inject a
    message onto any ticket."""
    settings.INBOUND_EMAIL_WEBHOOK_SECRET = ""
    response = _post(client, {"From": "a@b.example"}, secret="")
    assert response.status_code == 503
    assert not InboundMessageLog.objects.exists()


@pytest.mark.django_db
def test_malformed_json_is_rejected_not_crashed(configured, client, department, branch):
    response = client.post(
        reverse(WEBHOOK),
        data="not json at all",
        content_type="application/json",
        headers={"x-webhook-secret": SECRET},
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_the_webhook_is_reachable_without_signing_in(configured, client, department, branch):
    """It is exempt from deny-by-default on purpose — the sender is a provider, not a person.
    This pins that the exemption exists, since removing it would silently stop inbound mail."""
    response = _post(client, {"From": "someone@example.com", "Subject": "Hello", "TextBody": "Hi"})
    assert response.status_code == 200


# --- a message actually arriving ---


@pytest.mark.django_db
def test_a_reply_threads_onto_its_ticket(configured, client, ticket, category):
    response = _post(
        client,
        {
            "To": f"support+{ticket.reference}@example.com",
            "From": "sara@najd-trading.example",
            "Subject": "Re: still broken",
            "TextBody": "Any update on this?",
        },
    )
    assert response.status_code == 200
    assert response.json()["matched"] is True

    log = InboundMessageLog.objects.get()
    assert log.matched_ticket == ticket
    assert ticket.messages.filter(body="Any update on this?").exists()


@pytest.mark.django_db
def test_an_unthreadable_message_is_stored_and_answered_200(
    configured, client, department, branch, category
):
    """A 4xx would make the provider retry, duplicating a message that is already stored."""
    response = _post(client, {"From": "", "Subject": "No sender"})
    assert response.status_code == 200
    assert response.json()["stored"] is True

    log = InboundMessageLog.objects.get()
    assert log.processing_error


# --- the normalizer ---


def test_rfc822_arabic_subject_is_decoded():
    """Mail headers arrive RFC 2047-encoded; Arabic subjects arrive base64. Decoding them
    wrongly turns a subject into mojibake, which is invisible to anyone not reading Arabic."""
    raw = (
        b"From: Sara <sara@najd.example>\r\n"
        b"To: support@example.com\r\n"
        b"Subject: =?UTF-8?B?2YTZhSDZiti12YQg2KfZhNi02K3Zhg==?=\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
        b"\xd9\x84\xd9\x85 \xd9\x8a\xd8\xb5\xd9\x84 \xd8\xb4\xd9\x8a\xd8\xa1\r\n"
    )
    message = normalize_rfc822(raw)

    assert message["subject"] == "لم يصل الشحن"
    assert "لم يصل شيء" in message["body"]
    assert message["from"] == "sara@najd.example"


def test_rfc822_prefers_the_plain_text_part():
    raw = (
        b"From: a@b.example\r\nTo: support@example.com\r\nSubject: Multipart\r\n"
        b'Content-Type: multipart/alternative; boundary="XX"\r\n\r\n'
        b"--XX\r\nContent-Type: text/plain; charset=utf-8\r\n\r\nplain version\r\n"
        b"--XX\r\nContent-Type: text/html; charset=utf-8\r\n\r\n<p>html version</p>\r\n"
        b"--XX--\r\n"
    )
    assert "plain version" in normalize_rfc822(raw)["body"]
    assert "html version" not in normalize_rfc822(raw)["body"]


def test_webhook_payload_prefers_the_raw_message_when_present():
    """Using the provider's own parsed fields means trusting their parsing; the raw message
    keeps us on one code path whichever provider is in front."""
    raw = (
        b"From: a@b.example\r\nTo: support@example.com\r\nSubject: Raw wins\r\n"
        b"Content-Type: text/plain\r\n\r\nbody from raw\r\n"
    )
    message = WebhookAdapter.normalize_payload(
        {
            "RawEmail": raw.decode(),
            "Subject": "parsed loses",
            "TextBody": "parsed body",
        }
    )
    assert message["subject"] == "Raw wins"
    assert "body from raw" in message["body"]


def test_webhook_payload_falls_back_to_parsed_fields():
    message = WebhookAdapter.normalize_payload(
        {
            "To": "support@example.com",
            "From": "a@b.example",
            "Subject": "Parsed",
            "TextBody": "parsed body",
        }
    )
    assert message["subject"] == "Parsed"
    assert message["body"] == "parsed body"
