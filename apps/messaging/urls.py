from django.urls import path

from apps.messaging import views

app_name = "messaging"
urlpatterns = [
    path("inbound/", views.inbound_email_webhook, name="inbound_webhook"),
]
