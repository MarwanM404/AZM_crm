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
]
