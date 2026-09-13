from django.conf import settings
from django.contrib.auth import login, logout
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import activate
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods, require_POST

from apps.accounts.forms import SignInForm
from apps.accounts.models import User


def _adopt_language_chosen_before_signing_in(request, user):
    """Carry a pre-sign-in language choice onto the account (FR-014).

    Without this the switch on the sign-in screen is decorative: someone deliberately picks
    Arabic, signs in, and lands on an English page one request later, because
    `UserLanguageMiddleware` activates the stored preference and the stored preference knows
    nothing about the choice they just made.

    Only a deliberate choice overrides it. Somebody who signs in without touching the switch
    keeps the language they set last time, which is why this reads the cookie rather than the
    active language — the active language is set for every request, chosen or not.
    """
    chosen = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
    if not chosen or chosen == user.language:
        return
    if chosen not in {code for code, _label in settings.LANGUAGES}:
        return

    user.language = chosen
    user.save(update_fields=["language"])


@require_http_methods(["GET", "POST"])
def sign_in(request):
    if request.method == "POST":
        form = SignInForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data["user"]
            _adopt_language_chosen_before_signing_in(request, user)
            login(request, user)
            return redirect("tickets:queue")
    else:
        form = SignInForm()
    return render(
        request,
        "accounts/sign_in.html",
        {"form": form, "quick_sign_in_roles": _quick_sign_in_roles()},
    )


def _quick_sign_in_roles():
    """The roles the sign-in screen offers a one-click button for, or nothing at all.

    Empty unless the setting is on, so the controls cannot appear where the route would refuse
    them — but the route checks the setting itself and does not trust this. A hidden button is
    presentation; the refusal is the control (FR-018).
    """
    if not getattr(settings, "QUICK_SIGN_IN_ENABLED", False):
        return []

    labels = dict(User.Role.choices)
    return [
        (role, labels.get(role, role)) for role in getattr(settings, "QUICK_SIGN_IN_ACCOUNTS", {})
    ]


@require_http_methods(["POST"])
def sign_out(request):
    logout(request)
    return redirect("accounts:sign_in")


@require_http_methods(["POST"])
def set_language_for_user(request):
    """Switch interface language and return the user to the page they were on (FR-033).

    This used to answer 204 No Content, which a browser treats as "stay exactly where you
    are, change nothing" — so the switch appeared to do nothing until the page was reloaded
    by hand. Redirecting back to the current page makes the change take effect immediately,
    and works without JavaScript.
    """
    language = request.POST.get("language")
    valid_codes = {code for code, _ in request.user.Language.choices}
    if language not in valid_codes:
        return HttpResponse(status=400)

    request.user.language = language
    request.user.save(update_fields=["language"])
    activate(language)

    # Only ever return to a page on this site: `next` and Referer both come from the request,
    # so an unchecked redirect here is an open redirect.
    target = request.POST.get("next") or request.META.get("HTTP_REFERER") or ""
    if not url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        target = reverse("tickets:queue")

    response = redirect(target)
    response.set_cookie("django_language", language)
    return response


@require_http_methods(["POST"])
def set_language_anonymously(request):
    """Choose a language before there is an account to remember it (FR-012).

    Separate from `set_language_for_user`, which writes `request.user.language` and therefore
    needs the account the visitor is trying to reach. This writes the cookie the locale
    middleware reads for anonymous requests — the one mechanism that works before sign-in.

    Redirects rather than answering "nothing changed": this project already shipped a switch
    that returned 204, which a browser treats as "stay where you are", so it appeared to do
    nothing until the page was reloaded by hand.
    """
    language = request.POST.get("language")
    if language not in {code for code, _label in settings.LANGUAGES}:
        return HttpResponse(status=400)

    target = request.POST.get("next") or request.META.get("HTTP_REFERER") or ""
    if not url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        # `next` and Referer both come from the request, so an unchecked redirect here is an
        # open redirect on a page that anyone can reach without signing in.
        target = reverse("accounts:sign_in")

    response = redirect(target)
    response.set_cookie(
        settings.LANGUAGE_COOKIE_NAME,
        language,
        max_age=settings.LANGUAGE_COOKIE_AGE,
        path=settings.LANGUAGE_COOKIE_PATH,
        samesite="Lax",
    )
    activate(language)
    return response


@require_POST
def quick_sign_in(request, role):
    """Sign in as a demonstration account, for testing (FR-015).

    Every refusal below comes before anything else happens, and the order is the design.

    The setting is checked first. Hiding the control on the sign-in screen is presentation; it
    does not disable the route behind it, and a route that works when its control is hidden is
    a route somebody will find (FR-018). `config/settings/production.py` forces the setting off
    without reading the environment, so there is no deployment value that reaches this line
    with it on.

    The account is then looked up by name from configuration, never by role. "Sign me in as an
    agent" must not mean "whichever account happens to hold that role" — that is the difference
    between a convenience and an authentication bypass (FR-019).
    """
    if not getattr(settings, "QUICK_SIGN_IN_ENABLED", False):
        raise Http404

    email = getattr(settings, "QUICK_SIGN_IN_ACCOUNTS", {}).get(role)
    if email is None:
        raise Http404

    user = User.objects.filter(email=email, is_active=True).first()
    if user is None:
        # Deleted, renamed, or never seeded. It says so rather than signing somebody in as
        # whoever is nearest — a convenience that guesses is worse than one that stops.
        return HttpResponse(
            _(
                "There is no demonstration account for that role. Run the seed command, or "
                "sign in with an email address and a password."
            ),
            status=404,
        )

    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return redirect("tickets:queue")
