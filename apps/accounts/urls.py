from django.urls import path

from apps.accounts import views

app_name = "accounts"
urlpatterns = [
    path("sign-in/", views.sign_in, name="sign_in"),
    path("sign-out/", views.sign_out, name="sign_out"),
    path("language/", views.set_language_for_user, name="language"),
]
