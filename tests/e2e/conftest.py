"""
Fixtures for the browser-based right-to-left checks.

These are the only tests that need a real browser. They are marked `e2e` so a machine
without Playwright's browsers can run everything else with `-m "not e2e"`.
"""

import os

import pytest

# Playwright's sync API drives the browser from inside an event loop, and Django refuses ORM
# calls there by default. The guard exists to stop a blocking query stalling a production
# async view; in a test the queries are deliberate and the loop is Playwright's own, so it is
# correct to lift it here and nowhere else.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")


@pytest.fixture
def arabic_agent(db, django_user_model):
    from apps.accounts.models import Branch, Department

    department = Department.objects.create(name="Support", name_ar="الدعم")
    branch = Branch.objects.create(name="Head Office", name_ar="المكتب الرئيسي")
    return django_user_model.objects.create_user(
        email="layla@example.com",
        password="rtl-test-password",
        full_name="ليلى حسن",
        role=django_user_model.Role.AGENT,
        department=department,
        branch=branch,
        language="ar",
    )


@pytest.fixture
def rtl_fixtures(arabic_agent):
    """A ticket carrying both a public message and an internal note, so the note's edge can
    be measured in a real layout."""
    from apps.customers.services.matching import find_or_create_contact
    from apps.tickets.models import Category, Message, Ticket

    department, branch = arabic_agent.department, arabic_agent.branch
    category = Category.objects.create(
        name="Logistics", name_ar="الخدمات اللوجستية", department=department
    )
    contact, _ = find_or_create_contact(
        full_name="سارة أحمد",
        email="sara@najd.example",
        department=department,
        branch=branch,
    )
    ticket = Ticket.objects.create(
        contact=contact,
        subject="لم يصل الشحن رغم تسجيله كمُسلَّم",
        description="لم يصل شيء حتى الآن.",
        category=category,
        origin_channel=Ticket.Channel.WEB_FORM,
        department=department,
        branch=branch,
    )
    Message.objects.create(
        ticket=ticket,
        author=arabic_agent,
        direction=Message.Direction.OUTBOUND,
        visibility=Message.Visibility.INTERNAL,
        channel=ticket.origin_channel,
        body="توقيع الناقل لا يطابق أي جهة اتصال معروفة.",
    )
    return {"agent": arabic_agent, "ticket": ticket, "category": category}


@pytest.fixture
def signed_in_page(page, live_server, rtl_fixtures):
    """A browser page signed in as the Arabic-speaking agent."""
    page.goto(f"{live_server.url}/sign-in/")
    page.fill("input[name='email']", rtl_fixtures["agent"].email)
    page.fill("input[name='password']", "rtl-test-password")
    page.click("button[type='submit']")
    page.wait_for_load_state("networkidle")
    return page
