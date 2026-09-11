"""FR-035: Arabic content stored and re-rendered unchanged at the intake boundary."""

import time

import pytest
from django.urls import reverse

from apps.tickets.models import Ticket

ARABIC_SUBJECT = "المشكلة لا تزال قائمة"
ARABIC_DESCRIPTION = "لم يعمل النظام منذ الأمس، وأحتاج إلى مساعدة عاجلة."


@pytest.mark.django_db
def test_arabic_subject_and_description_survive_round_trip(client, branch, category):
    payload = {
        "full_name": "سارة أحمد",
        "email": "sara@example.com",
        "category": category.pk,
        "subject": ARABIC_SUBJECT,
        "description": ARABIC_DESCRIPTION,
        "company_website": "",
        "rendered_at": time.time() - 5,
    }
    response = client.post(reverse("intake:form"), payload)
    assert response.status_code == 302

    ticket = Ticket.objects.get()
    assert ticket.subject == ARABIC_SUBJECT
    assert ticket.description == ARABIC_DESCRIPTION
    assert ticket.contact.full_name == "سارة أحمد"
