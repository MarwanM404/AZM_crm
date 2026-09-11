"""FR-035: Arabic customer content renders correctly inside the English interface."""

import pytest
from django.urls import reverse

ARABIC_SUBJECT = "لم يصل الشحن رغم تسجيله كمُسلَّم"
ARABIC_BODY = "لم يصل شيء حتى الآن، ونحتاج القطع قبل الأحد."


@pytest.fixture
def arabic_ticket(ticket):
    ticket.subject = ARABIC_SUBJECT
    ticket.description = ARABIC_BODY
    ticket.save(update_fields=["subject", "description"])
    return ticket


@pytest.mark.django_db
def test_arabic_content_renders_in_the_english_queue(client, agent, arabic_ticket):
    agent.language = "en"
    agent.save(update_fields=["language"])
    client.force_login(agent)

    body = client.get(reverse("tickets:queue")).content.decode()

    assert 'dir="ltr"' in body  # the interface stays English
    assert ARABIC_SUBJECT in body  # the customer's words are unchanged


@pytest.mark.django_db
def test_arabic_content_renders_on_the_english_detail_page(client, agent, arabic_ticket):
    agent.language = "en"
    agent.save(update_fields=["language"])
    client.force_login(agent)

    body = client.get(reverse("tickets:detail", args=[arabic_ticket.reference])).content.decode()
    assert ARABIC_SUBJECT in body


@pytest.mark.django_db
def test_reference_stays_left_to_right_in_the_arabic_interface(client, agent, arabic_ticket):
    """A ticket reference inside Arabic text must not have its segments reordered. The `ref`
    class pins direction; this asserts the markup that carries it is actually applied."""
    agent.language = "ar"
    agent.save(update_fields=["language"])
    client.force_login(agent)

    body = client.get(reverse("tickets:queue")).content.decode()

    assert 'dir="rtl"' in body
    assert arabic_ticket.reference in body
    assert 'class="ref"' in body
