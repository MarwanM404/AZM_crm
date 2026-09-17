"""
The pre-chat form offers category names in the reader's language (MVP FR-031).

`Category.__str__` returns the English name, which is correct for the Django admin, the audit
log and every log line — and wrong on a form a customer fills in. An Arabic visitor opening
live chat was offered "Logistics" and "Billing" between labels reading الفئة and ما الذي
نساعدك فيه؟.

The intake form and the portal's new-request form were fixed in spec 004; this one was missed,
and stayed missed because no browser check covered the chat widget. It failed on the first run
of the public Arabic sweep — a unit test cannot see it, because every category renders and the
form validates either way.

Kept as a unit test as well as a browser one: this is the third form to need the same line, and
the next person adding a fourth should find the reason next to the code rather than in an e2e
file that takes seventy seconds to run.
"""

import pytest
from django.utils import translation

from apps.chat.forms import PreChatForm
from apps.tickets.models import Category

pytestmark = pytest.mark.django_db


def test_an_arabic_reader_is_offered_arabic_names(department):
    Category.objects.create(name="Billing", name_ar="الفوترة", department=department)

    with translation.override("ar"):
        rendered = str(PreChatForm()["category"])

    assert "الفوترة" in rendered
    assert ">Billing<" not in rendered


def test_an_english_reader_is_offered_english_names(department):
    """So the rule cannot be satisfied by always showing the Arabic name."""
    Category.objects.create(name="Billing", name_ar="الفوترة", department=department)

    with translation.override("en"):
        rendered = str(PreChatForm()["category"])

    assert ">Billing<" in rendered


def test_a_category_with_no_arabic_name_still_appears(department):
    """`name_ar` may be blank. An untranslated category should read oddly, not vanish — a
    customer who cannot choose it cannot ask about that thing at all."""
    Category.objects.create(name="Untranslated", name_ar="", department=department)

    with translation.override("ar"):
        rendered = str(PreChatForm()["category"])

    assert ">Untranslated<" in rendered
