"""
The customer portal's routes (T002).

Every path here is served to somebody outside the organization, which is the opposite of
every other URL configuration in this project. Three consequences follow, none of them
assumed here: templates/portal/ is swept for internal content by directory
(tests/test_internal_visibility.py), a staff session is refused at the door
(apps/portal/middleware.py), and the namespace below is what
apps/core/middleware.py uses to decide that a customer session is allowed through the
deny-by-default wall — so renaming it silently locks every customer out.
"""

from django.urls import path

from apps.portal import views

app_name = "portal"

urlpatterns = [
    path("", views.home, name="home"),
    path("language/", views.set_language, name="language"),
    path("requests/<str:reference>/", views.request_detail, name="request"),
    # Reachable without a session. Each is justified by name in
    # settings.LOGIN_EXEMPT_URL_NAMES, which apps/accounts/tests/test_anonymous_access.py
    # pins exactly — so one cannot be added here and quietly left off that list, nor added to
    # that list without a written reason.
    path("register/", views.register, name="register"),
    path("register/done/", views.register_done, name="register_done"),
    path("confirm/<str:value>/", views.confirm, name="confirm"),
    # NOT under confirm/. It was, and `confirm/<str:value>/` matched it first with
    # value="resend" — so asking for another confirmation answered "this link no longer
    # works", which is both wrong and the most discouraging possible reply to somebody whose
    # link has expired. Ordering the patterns the other way would also fix it and would leave
    # the trap in place for the next path added under confirm/; a prefix that cannot collide
    # removes it.
    path("resend/", views.resend_confirmation, name="resend_confirmation"),
    path("sign-in/", views.sign_in, name="sign_in"),
    path("sign-out/", views.sign_out, name="sign_out"),
]
