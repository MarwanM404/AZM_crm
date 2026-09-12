from django.contrib.auth import login, logout
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import activate
from django.views.decorators.http import require_http_methods

from apps.accounts.forms import SignInForm


@require_http_methods(["GET", "POST"])
def sign_in(request):
    if request.method == "POST":
        form = SignInForm(request.POST)
        if form.is_valid():
            login(request, form.cleaned_data["user"])
            return redirect("tickets:queue")
    else:
        form = SignInForm()
    return render(request, "accounts/sign_in.html", {"form": form})


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
