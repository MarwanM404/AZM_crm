from django.urls import path

from apps.tickets import views

app_name = "tickets"
urlpatterns = [
    path("", views.queue, name="queue"),
    path("<str:reference>/", views.detail, name="detail"),
    path("<str:reference>/take/", views.take, name="take"),
    path("<str:reference>/assign/", views.assign, name="assign"),
    path("<str:reference>/status/", views.status, name="status"),
    path("<str:reference>/fields/", views.fields, name="fields"),
    path("<str:reference>/reply/", views.reply, name="reply"),
    path("<str:reference>/note/", views.note, name="note"),
]
