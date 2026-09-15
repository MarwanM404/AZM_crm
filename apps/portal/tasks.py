"""
The portal's outbound mail (T038).

Follows apps/messaging/tasks.py: queued with retry, composed inside
`translation.override(language)` so the message is written in the RECIPIENT's language rather
than in whatever happened to be active on the thread that queued it. That distinction is not
theoretical — a customer registering in Arabic is served by a request running in Arabic, but
the task may run minutes later on a worker that is not.

None of these tasks take an actor. There is no acting user: the person who caused the send is
the anonymous visitor who typed an address into a public form, and recording them as the
actor on an audited write would be recording a guess.
"""

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import translation


def _absolute(path):
    """A link in an email cannot be relative, and the site has no request to ask.

    `PORTAL_BASE_URL` is a setting rather than `Sites` or a guess from the request: the
    request that triggers this is gone by the time the worker runs, and a link built from a
    Host header is a link an attacker can point wherever they like — in a message our own
    mail server sends, carrying our own reputation.
    """
    return f"{settings.PORTAL_BASE_URL.rstrip('/')}{path}"


def _send(to, subject, template, context, language):
    with translation.override(language):
        body = render_to_string(template.format(language=language), context)
        EmailMultiAlternatives(
            subject=translation.gettext(subject),
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to],
        ).send(fail_silently=False)


@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def send_confirmation(self, *, email, token_value, language):
    try:
        _send(
            to=email,
            subject="Confirm your email address",
            template="portal/email/confirm.{language}.txt",
            context={"link": _absolute(reverse("portal:confirm", args=[token_value]))},
            language=language,
        )
    except Exception as exc:
        raise self.retry(exc=exc) from exc


@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def send_already_registered(self, *, email, language):
    """FR-008. Sent to the owner of an address somebody else has just tried to register.

    Carries no link and no password — not the one that was typed, not a confirmation, not a
    reset. Whoever triggered this message did so by typing a stranger's address into a public
    form, and anything actionable in it would make that an attack rather than a nuisance.
    """
    try:
        _send(
            to=email,
            subject="Somebody tried to register your email address",
            template="portal/email/already_registered.{language}.txt",
            context={"sign_in": _absolute(reverse("portal:sign_in"))},
            language=language,
        )
    except Exception as exc:
        raise self.retry(exc=exc) from exc


@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def send_reset(self, *, email, token_value, language):
    try:
        _send(
            to=email,
            subject="Reset your password",
            template="portal/email/reset.{language}.txt",
            context={"link": _absolute(reverse("portal:reset_confirm", args=[token_value]))},
            language=language,
        )
    except Exception as exc:
        raise self.retry(exc=exc) from exc


@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def send_locked_out(self, *, email, language, minutes):
    """FR-011. Sent once, when an account locks — never on the attempts afterwards.

    Carries no link and no unlock action. Whoever triggered this was guessing a password;
    anything actionable in the message they caused to be sent would hand them a second route
    in. The owner's route in is the reset flow, which they can reach on their own.
    """
    try:
        _send(
            to=email,
            subject="Your account was locked after repeated sign-in attempts",
            template="portal/email/locked_out.{language}.txt",
            context={"minutes": minutes, "reset": _absolute(reverse("portal:reset"))},
            language=language,
        )
    except Exception as exc:
        raise self.retry(exc=exc) from exc
