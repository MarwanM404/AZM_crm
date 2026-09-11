from django.urls import path

from apps.accounts import views_admin
from apps.core import views as core_views

app_name = "administration"
urlpatterns = [
    path("users/", views_admin.user_list, name="users"),
    path("users/new/", views_admin.user_new, name="user_new"),
    path("users/<int:pk>/scope/", views_admin.user_scope, name="user_scope"),
    path("users/<int:pk>/deactivate/", views_admin.user_deactivate, name="user_deactivate"),
    path("audit/", core_views.audit_log, name="audit"),
]
