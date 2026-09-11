from django.urls import path

from apps.customers import views

app_name = "customers"
urlpatterns = [
    path("", views.organization_list, name="list"),
    path("unlinked/", views.unlinked_contacts, name="unlinked"),
    path("contacts/<int:pk>/link/", views.link, name="link_contact"),
    path("contacts/<int:pk>/edit/", views.edit_contact, name="edit_contact"),
    path("<int:pk>/", views.organization_detail, name="detail"),
    path("<int:pk>/edit/", views.edit_organization, name="edit"),
    path("<int:pk>/note/", views.add_note, name="note"),
    path("<int:pk>/delete/", views.delete_organization, name="delete"),
]
