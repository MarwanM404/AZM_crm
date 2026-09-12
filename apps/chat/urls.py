from django.urls import path

from apps.chat import views

app_name = "chat"
urlpatterns = [
    path("availability/", views.availability, name="availability"),
    path("widget/", views.widget, name="widget"),
    path("start/", views.start, name="start"),
    path("leave-queue/", views.leave_queue, name="leave_queue"),
]
