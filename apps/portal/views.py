"""
The portal's views.

Only the landing page exists at this stage. It is here rather than in User Story 1 because
the foundation needs something to guard: a decorator with nothing behind it, a middleware
with no path to act on, and a refusal test with an empty route list all report working
without having been exercised. This project has shipped that exact shape before.

The list of requests replaces this page in User Story 2 (T052).
"""

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import activate
from django.views.decorators.http import require_http_methods

from apps.portal.auth import customer_required


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
