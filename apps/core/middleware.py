"""
Deny-by-default authorization middleware (constitution: Security & Access Control;
FR-021: absence of a check is a failure, not a permissive default).

Placed after AuthenticationMiddleware in MIDDLEWARE so request.user is resolved, and after
django_htmx so htmx requests are covered identically to full-page ones. Every path is denied
to anonymous users except the explicit exemptions in settings.LOGIN_EXEMPT_URL_NAMES.
"""

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.urls import resolve


class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            return self.get_response(request)

        if self._is_asset(request.path_info):
            return self.get_response(request)

        try:
            match = resolve(request.path_info)
            url_name = f"{match.namespace}:{match.url_name}" if match.namespace else match.url_name
        except Exception:
            url_name = None

        if url_name in settings.LOGIN_EXEMPT_URL_NAMES:
            return self.get_response(request)

        return redirect_to_login(request.get_full_path(), login_url=settings.LOGIN_URL)

    @staticmethod
    def _is_asset(path):
        """Static and media files are not views: they resolve to no URL name, so the
        deny-by-default rule would redirect them to sign-in. In development, where Django
        serves them, that leaves the public request form with no stylesheet for exactly the
        people it exists for — anonymous customers.

        The prefixes are checked rather than trusted. Django's MEDIA_URL defaults to "/",
        and a prefix of "/" matches every path on the site — exempting it would switch
        authentication off entirely. Only a prefix that actually names a subdirectory is
        usable here.
        """
        for prefix in (settings.STATIC_URL, getattr(settings, "MEDIA_URL", None)):
            if prefix and prefix not in ("", "/") and path.startswith(prefix):
                return True
        return False


class UserLanguageMiddleware:
    """
    Activate the signed-in user's stored language (FR-033).

    Django's LocaleMiddleware resolves language from the URL, the session, a cookie, then the
    Accept-Language header. It knows nothing about a language stored on the user record, so
    without this the preference is written and never read — which is what "persists across
    sessions" actually requires.

    Must sit after AuthenticationMiddleware (request.user has to be resolved) and after
    LocaleMiddleware, whose choice this deliberately overrides for authenticated users.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.conf import settings
        from django.utils import translation

        user = getattr(request, "user", None)
        language = getattr(user, "language", None) if user and user.is_authenticated else None

        if language and language in dict(settings.LANGUAGES):
            translation.activate(language)
            request.LANGUAGE_CODE = language

        return self.get_response(request)
