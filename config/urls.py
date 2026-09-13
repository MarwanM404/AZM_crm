from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.views.i18n import JavaScriptCatalog

urlpatterns = [
    # Django's own admin moves aside: contracts/http-endpoints.md gives /admin/ to the staff
    # screens, which Django's admin cannot provide (it records no refused attempts and has
    # no session-terminating deactivation — FR-021, FR-026).
    path("django-admin/", admin.site.urls),
    # Client-side translations (FR-007). `gettextOrFallback` in static/js/chat-console.js has
    # always looked for `window.gettext` and never found one, because this was never routed —
    # so the fallback was not a fallback, it was the only path, and an Arabic agent read
    # "Online" and "Offline" on an otherwise Arabic screen.
    #
    # Served per request rather than cached: the catalog depends on the active language, and
    # a cached one would hand an Arabic agent the English strings — the same defect, in a
    # place that now looks handled.
    path("jsi18n/", JavaScriptCatalog.as_view(), name="javascript-catalog"),
    path("admin/", include("apps.accounts.urls_admin")),
    path("email/", include("apps.messaging.urls")),
    path("", include("apps.intake.urls")),
    path("", include("apps.accounts.urls")),
    path("tickets/", include("apps.tickets.urls")),
    path("customers/", include("apps.customers.urls")),
    path("attachments/", include("apps.attachments.urls")),
    path("chat/", include("apps.chat.urls")),
]

if settings.DEBUG:
    from django.conf.urls.static import static

    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)  # type: ignore[arg-type]
