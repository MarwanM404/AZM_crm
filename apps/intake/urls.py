from django.urls import path

from apps.intake import views

app_name = "intake"
urlpatterns = [
    path("request/", views.request_form, name="form"),
    path("request/submitted/<str:reference>/", views.submitted, name="submitted"),
]
