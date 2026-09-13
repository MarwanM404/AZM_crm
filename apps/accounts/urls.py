from django.urls import path

from apps.accounts import views

app_name = "accounts"
urlpatterns = [
    path("sign-in/", views.sign_in, name="sign_in"),
    path("sign-out/", views.sign_out, name="sign_out"),
    path("sign-in/as/<str:role>/", views.quick_sign_in, name="quick_sign_in"),
    path("language/", views.set_language_for_user, name="language"),
    path("language/choose/", views.set_language_anonymously, name="anonymous_language"),
]
