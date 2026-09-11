from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    # Django's own admin moves aside: contracts/http-endpoints.md gives /admin/ to the staff
    # screens, which Django's admin cannot provide (it records no refused attempts and has
    # no session-terminating deactivation — FR-021, FR-026).
    path("django-admin/", admin.site.urls),
    path("admin/", include("apps.accounts.urls_admin")),
    path("", include("apps.intake.urls")),
    path("", include("apps.accounts.urls")),
    path("tickets/", include("apps.tickets.urls")),
    path("customers/", include("apps.customers.urls")),
]

if settings.DEBUG:
    from django.conf.urls.static import static

    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)  # type: ignore[arg-type]
