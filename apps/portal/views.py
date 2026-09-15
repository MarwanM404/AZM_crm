"""
The portal's views (T035, T036).

Three of these are public and are the only screens in this product, other than the request
form, that an anonymous stranger can reach. Two rules govern all of them and are easier to
hold here than to remember per view:

  * the response never depends on whether an address is known (FR-007), which is why the
    outcome-free services in apps/portal/services/registration.py return nothing at all; and
  * every one is rate limited per address AND per source (FR-010), from settings rather than
    from literals, so the numbers can be changed on the day they are needed rather than in
    the next release.

Rate limiting fails OPEN, matching apps/intake/views.py and research.md #6: a Redis outage
must not turn away genuine customers. What that costs is real and is worth naming — while
Redis is down, these screens are unprotected, and the account lockout (User Story 5) is the
defence that does not depend on it.
"""

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import translation
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import activate
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit

from apps.portal import auth
from apps.portal.auth import Unconfirmed, customer_required
from apps.portal.forms import EmailForm, RegistrationForm, SignInForm
from apps.portal.services import registration

#: Limits count POSTs and nothing else.
#:
#: django-ratelimit's default is `method=ALL`, which counts GETs too — so simply opening the
#: registration page enough times exhausts the quota and the screen refuses somebody who has
#: not yet typed anything. Found by driving the pages in a browser: a script that loaded each
#: screen a handful of times to photograph it was rate-limited out of registering at all.
#:
#: Counting reads also makes the per-address key meaningless on a GET, where there is no
#: address to key on.
POST_ONLY = "POST"


def _rate(setting_name):
    """Read the limit from settings at request time, not at import time.

    A decorator argument is evaluated once, when the module is imported — so a literal here
    would need a deployment to change and the `settings` fixture could not move it in a test.
    django-ratelimit accepts a callable for exactly this.
    """
    return lambda group, request: getattr(settings, setting_name)


PERIODS = {
    "s": lambda: _("Please try again in a minute."),
    "m": lambda: _("Please try again in a few minutes."),
    "h": lambda: _("Please try again in an hour."),
    "d": lambda: _("Please try again tomorrow."),
}


def too_many(request, rate_setting):
    """One page for every limited screen, deliberately identical whatever was submitted.

    It echoes nothing back — not the address, not the form. Re-rendering the form with the
    submitted address would make two refusals differ by the thing the customer typed, and
    `test_a_refusal_does_not_reveal_whether_the_address_is_known` compares them as bytes.
    Not echoing also means the page cannot be resubmitted by reflex, which is the behaviour
    the limit exists to interrupt.
    """
    rate = getattr(settings, rate_setting, "5/h")
    period = rate.rsplit("/", 1)[-1][-1:]
    return render(
        request,
        "portal/too_many.html",
        {"try_again": PERIODS.get(period, PERIODS["h"])()},
        status=429,
    )


@customer_required
def home(request):
    return render(request, "portal/home.html", {"customer": request.customer})


@require_http_methods(["POST"])
@customer_required
def set_language(request):
    """Switch language and remember it on the account.

    The portal needs its own version of this for the same reason it needs its own sign-in:
    `accounts:set_language_for_user` writes `request.user.language`, and a customer is never
    `request.user`.

    Posting to the anonymous switch instead is not an option, and the reason is worth
    recording because it was shipped that way for an hour and looked fine. The anonymous
    switch writes a cookie, which the locale middleware reads — but
    `CustomerSessionMiddleware` then activates the language stored on the account, which
    overrides it. The result is a switch that highlights the language the customer did not
    pick and changes nothing on the page: a control that visibly does nothing, which is worse
    than no control. Found by clicking it in a browser; no test noticed.
    """
    language = request.POST.get("language")
    if language not in {code for code, _label in settings.LANGUAGES}:
        return HttpResponse(status=400)

    request.customer.language = language
    request.customer.save(update_fields=["language", "updated_at"])
    activate(language)

    # `next` and Referer both come from the request, so an unchecked redirect here is an open
    # redirect — on a page reachable by anyone who can register.
    target = request.POST.get("next") or request.META.get("HTTP_REFERER") or ""
    if not url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        target = reverse("portal:home")

    return redirect(target)


# --- registering, and proving the address (User Story 1) ---


@require_http_methods(["GET", "POST"])
@ratelimit(key="ip", rate=_rate("PORTAL_REGISTER_RATE_PER_SOURCE"), method=POST_ONLY, block=False)
@ratelimit(
    key="post:email", rate=_rate("PORTAL_REGISTER_RATE_PER_ADDRESS"), method=POST_ONLY, block=False
)
def register(request):
    """FR-001, FR-007.

    Note what this view cannot do: branch on whether the address is known. `registration
    .register` returns nothing, so there is no outcome to render differently even by mistake.
    Every successful POST ends at the same redirect, whether an account was created, a notice
    was sent to somebody else, or nothing happened at all.
    """
    if getattr(request, "limited", False):
        return too_many(request, "PORTAL_REGISTER_RATE_PER_SOURCE")

    form = RegistrationForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        registration.register(
            email=form.cleaned_data["email"],
            password=form.cleaned_data["password"],
            language=translation.get_language() or settings.LANGUAGE_CODE,
        )
        return redirect("portal:register_done")

    return render(request, "portal/register.html", {"form": form})


def register_done(request):
    """ "Check your email." Says nothing about whether an account was created, because the
    person reading it may not be the person who owns the address."""
    return render(request, "portal/register_done.html", {})


def confirm(request, value):
    """FR-002, FR-004. A GET that changes state, which is right here and nowhere else.

    Mail clients follow links; they do not submit forms. What makes it safe is not the method
    but the token: unguessable, single use, expiring, and able to do exactly one thing.
    """
    account = registration.confirm(value)

    if account is None:
        # 200, not 400. The request is well formed; the token is simply spent, which is the
        # normal end of a link that did its job. A 400 here would mark an ordinary event as a
        # client error in every log and monitor, and the page is read by a person rather than
        # a machine. Django's own invalid-reset page answers the same way.
        return render(request, "portal/confirm_failed.html", {})

    auth.sign_in_customer(request, account)
    return redirect("portal:home")


@require_http_methods(["GET", "POST"])
@ratelimit(
    key="ip", rate=_rate("PORTAL_CONFIRM_RESEND_RATE_PER_SOURCE"), method=POST_ONLY, block=False
)
@ratelimit(
    key="post:email",
    rate=_rate("PORTAL_CONFIRM_RESEND_RATE_PER_ADDRESS"),
    method=POST_ONLY,
    block=False,
)
def resend_confirmation(request):
    """Another message, for the one that went to spam or expired.

    Answers identically for an address with no account. This screen sends mail to an address
    on request, so without the limit above it is a way to send somebody a hundred emails
    using our mail server and our reputation.
    """
    if getattr(request, "limited", False):
        return too_many(request, "PORTAL_CONFIRM_RESEND_RATE_PER_SOURCE")

    form = EmailForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        registration.resend_confirmation(form.cleaned_data["email"])
        return redirect("portal:register_done")

    return render(request, "portal/resend_confirmation.html", {"form": form})


# --- signing in and out ---


@require_http_methods(["GET", "POST"])
@ratelimit(key="ip", rate=_rate("PORTAL_SIGN_IN_RATE_PER_SOURCE"), method=POST_ONLY, block=False)
@ratelimit(
    key="post:email", rate=_rate("PORTAL_SIGN_IN_RATE_PER_ADDRESS"), method=POST_ONLY, block=False
)
def sign_in(request):
    """The one screen in this feature that deliberately discloses something.

    An account that exists but has not confirmed its address is told so, rather than being
    told the password is wrong — but ONLY to somebody who supplied the correct password. That
    ordering is the whole of the argument: with the password you are almost certainly the
    person who set it minutes ago; without it, the same message would say "this address has
    an account here".
    """
    if getattr(request, "limited", False):
        return too_many(request, "PORTAL_SIGN_IN_RATE_PER_SOURCE")

    form = SignInForm(request.POST or None)
    unconfirmed = False
    failed = False

    if request.method == "POST" and form.is_valid():
        try:
            account = auth.authenticate_customer(
                form.cleaned_data["email"], form.cleaned_data["password"]
            )
        except Unconfirmed:
            unconfirmed = True
        else:
            if account is not None:
                auth.sign_in_customer(request, account)
                return redirect("portal:home")
            failed = True

    return render(
        request,
        "portal/sign_in.html",
        {"form": form, "unconfirmed": unconfirmed, "failed": failed},
    )


@require_http_methods(["POST"])
def sign_out(request):
    auth.sign_out_customer(request)
    return redirect("portal:sign_in")
