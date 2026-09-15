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


# --- a live ASGI server, for the tests that need real WebSockets ---
#
# pytest-django's `live_server` is WSGI, so a page served by it can render the chat widget and
# then fail to open a socket — which would make a two-party chat test pass or fail for reasons
# unrelated to chat. Channels' own ChannelsLiveServerTestCase runs Daphne in a separate
# PROCESS and refuses SQLite, so it cannot be used here either.
#
# This runs uvicorn on a thread in the same process. It works because the test database is a
# file rather than in-memory (config/settings/test.py), so the server thread opens the same
# database; tests using it must therefore be `transaction=True`, or nothing they write is
# committed for the server to read.


@pytest.fixture
def asgi_live_server():
    import socket
    import threading
    import time

    import uvicorn
    from channels.routing import ProtocolTypeRouter
    from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler

    from config.asgi import application as configured

    # `runserver` serves static files through a handler it inserts itself; uvicorn does not,
    # so without this the page loads and every stylesheet and script 404s — the widget renders
    # unstyled and Alpine never runs, which looks exactly like a chat bug.
    application = ProtocolTypeRouter(
        {
            "http": ASGIStaticFilesHandler(configured.application_mapping["http"]),
            "websocket": configured.application_mapping["websocket"],
        }
    )

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    server = uvicorn.Server(
        uvicorn.Config(application, host="127.0.0.1", port=port, log_level="error")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.monotonic() + 15
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    if not server.started:
        server.should_exit = True
        pytest.skip("the ASGI test server did not start")

    class _Server:
        url = f"http://127.0.0.1:{port}"

    yield _Server()

    server.should_exit = True
    thread.join(timeout=10)


@pytest.fixture
def chat_fixtures(rtl_fixtures):
    """An Arabic conversation carrying a public message and a supervisor's private note, so
    both can be measured in a real layout."""
    from django.utils import timezone

    from apps.accounts.models import User
    from apps.chat.models import Conversation
    from apps.chat.services import presence
    from apps.chat.services.redis_client import reset_for_tests
    from apps.customers.services.matching import find_or_create_contact
    from apps.tickets.models import Message, Ticket

    reset_for_tests()
    agent = rtl_fixtures["agent"]
    department, branch = agent.department, agent.branch
    supervisor = User.objects.create_user(
        email="lead@example.com",
        password="rtl-test-password",
        full_name="فهد المطيري",
        role=User.Role.SUPERVISOR,
        department=department,
        branch=branch,
        language="ar",
    )
    contact, _ = find_or_create_contact(
        full_name="سارة أحمد",
        email="sara@najd.example",
        department=department,
        branch=branch,
    )
    ticket = Ticket.objects.create(
        contact=contact,
        subject="لم يصل الشحن",
        description="",
        category=rtl_fixtures["category"],
        origin_channel=Ticket.Channel.CHAT,
        department=department,
        branch=branch,
    )
    conversation = Conversation.objects.create(
        ticket=ticket,
        contact=contact,
        visitor_token_hash="e2e",
        department=department,
        branch=branch,
        assigned_to=agent,
        state=Conversation.State.ACTIVE,
        assigned_at=timezone.now(),
    )
    Message.objects.create(
        ticket=ticket,
        author=None,
        direction=Message.Direction.INBOUND,
        visibility=Message.Visibility.PUBLIC,
        channel=Ticket.Channel.CHAT,
        body="لم يصل الشحن رغم تسجيله كمُسلَّم.",
    )
    Message.objects.create(
        ticket=ticket,
        author=supervisor,
        direction=Message.Direction.OUTBOUND,
        visibility=Message.Visibility.INTERNAL,
        channel=Ticket.Channel.CHAT,
        body="لا تَعِد باسترداد المبلغ، تغيّرت السياسة يوم الأحد.",
    )
    presence.go_online(agent.pk, capacity=3)
    yield {
        "agent": agent,
        "supervisor": supervisor,
        "conversation": conversation,
        "ticket": ticket,
    }
    reset_for_tests()


@pytest.fixture
def arabic_administrator(rtl_fixtures):
    """An administrator in the same scope as `arabic_agent`.

    Needed because the administration screens refuse an agent with 403 — and a page reading
    "403 Forbidden" passes a sweep looking for English text or placeholder codes, so a sweep
    run as an agent reports those screens clean without ever rendering them.
    """
    from apps.accounts.models import User

    agent = rtl_fixtures["agent"]
    return User.objects.create_user(
        email="admin.rtl@example.com",
        password="rtl-test-password",
        full_name="مسؤول النظام",
        role=User.Role.ADMINISTRATOR,
        department=agent.department,
        branch=agent.branch,
        language="ar",
    )


@pytest.fixture
def admin_page(browser, live_server, arabic_administrator):
    page = browser.new_page()
    page.goto(f"{live_server.url}/sign-in/")
    page.fill("input[name='email']", arabic_administrator.email)
    page.fill("input[name='password']", "rtl-test-password")
    page.click("button[type='submit']")
    page.wait_for_load_state("networkidle")
    yield page
    page.close()


# --- the customer portal (spec 004) ---
#
# A customer needs its own page fixture: `signed_in_page` signs in as STAFF, and the whole
# design of the portal is that a staff session reaches none of it. A test that reused it would
# be photographing the 403 page.


@pytest.fixture
def portal_fixtures(arabic_agent):
    """An Arabic-speaking customer with a history, including an internal note.

    The note is the reason this fixture exists rather than a bare account: the sweeps below
    are looking for what a customer can see, and a screen with nothing hidden on it proves
    nothing about hiding.
    """
    from apps.customers.services.matching import find_or_create_contact
    from apps.portal.models import CustomerAccount
    from apps.tickets.models import Category, Message, Ticket

    department, branch = arabic_agent.department, arabic_agent.branch
    category = Category.objects.create(
        name="Logistics", name_ar="الخدمات اللوجستية", department=department
    )

    account = CustomerAccount.objects.create_account(
        email="noura@example.com", password="a-long-enough-passphrase-42", language="ar"
    )
    account.confirm()

    contact, _ = find_or_create_contact(
        full_name="نورة الحربي", email=account.email, department=department, branch=branch
    )
    ticket = Ticket.objects.create(
        contact=contact,
        subject="الشحنة مسجّلة كمُسلّمة ولم تصل",
        description="قيل لنا إنها شُحنت يوم الثلاثاء ولم يصل شيء حتى الآن.",
        category=category,
        origin_channel=Ticket.Channel.WEB_FORM,
        department=department,
        branch=branch,
    )
    Message.objects.create(
        ticket=ticket,
        author=arabic_agent,
        direction=Message.Direction.OUTBOUND,
        visibility=Message.Visibility.PUBLIC,
        channel=Ticket.Channel.EMAIL,
        body="نتابع مع شركة الشحن وسنوافيك بالمستجدات اليوم.",
    )
    Message.objects.create(
        ticket=ticket,
        author=arabic_agent,
        direction=Message.Direction.OUTBOUND,
        visibility=Message.Visibility.INTERNAL,
        channel=Ticket.Channel.EMAIL,
        body="INTERNAL-NOTE-THE-CUSTOMER-MUST-NEVER-SEE",
    )
    return {"account": account, "contact": contact, "ticket": ticket, "category": category}


@pytest.fixture
def portal_page(page, live_server, portal_fixtures):
    """A browser page holding a real customer session.

    The session is written directly rather than driven through the sign-in form: these tests
    are about layout, language and accessibility, and a fixture that goes through a screen
    fails for two different reasons.
    """
    from django.conf import settings
    from django.contrib.sessions.backends.db import SessionStore

    from apps.portal.auth import CUSTOMER_SESSION_FINGERPRINT, CUSTOMER_SESSION_KEY

    account = portal_fixtures["account"]
    session = SessionStore()
    session[CUSTOMER_SESSION_KEY] = account.pk
    session[CUSTOMER_SESSION_FINGERPRINT] = account.session_fingerprint
    session.save()

    # The cookie can only be set against an origin the context has seen.
    page.goto(f"{live_server.url}/portal/sign-in/")
    page.context.add_cookies(
        [
            {
                "name": settings.SESSION_COOKIE_NAME,
                "value": session.session_key,
                "url": live_server.url,
            }
        ]
    )
    return page
