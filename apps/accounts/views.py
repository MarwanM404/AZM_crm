from django.contrib.auth import login, logout
from django.http import HttpResponse
from django.shortcuts import redirect, render
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
    """FR-033: persist the choice on the user profile, not only the session, so it survives
    across devices and sign-ins."""
    language = request.POST.get("language")
    valid_codes = {code for code, _ in request.user.Language.choices}
    if language not in valid_codes:
        return HttpResponse(status=400)
    request.user.language = language
    request.user.save(update_fields=["language"])
    activate(language)
    response = HttpResponse(status=204)
    response.set_cookie("django_language", language)
    return response
