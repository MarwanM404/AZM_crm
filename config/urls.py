from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.intake.urls")),
    path("", include("apps.accounts.urls")),
    path("tickets/", include("apps.tickets.urls")),
    path("customers/", include("apps.customers.urls")),
]

if settings.DEBUG:
    from django.conf.urls.static import static

    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)  # type: ignore[arg-type]
