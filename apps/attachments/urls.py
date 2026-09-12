from django.urls import path

from apps.attachments import views

app_name = "attachments"
urlpatterns = [
    path("<int:pk>/", views.download, name="download"),
]
