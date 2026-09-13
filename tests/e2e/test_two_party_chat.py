"""
Two real browsers, one conversation (T121).

Every other test in this feature watches one end. This is the only one that exercises what two
people actually experience: a customer types, an agent sees it appear, the agent replies, and
the customer sees that — through real sockets, real rendering, and a real server.

It needs a live ASGI server, because a WSGI one serves the page and then silently fails to
open a socket. See `asgi_live_server` in conftest.py for why Channels' own live-server helper
could not be used.

`transaction=True` is not optional here: the server runs on its own thread and reads the
database file directly, so anything left in an uncommitted transaction does not exist as far
as it is concerned.
"""

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


@pytest.fixture
def desk_open(arabic_agent):
    """An agent online with room, which is what makes chat offered at all (FR-039)."""
    from apps.chat.services import presence
    from apps.chat.services.redis_client import reset_for_tests

    reset_for_tests()
    presence.go_online(arabic_agent.pk, capacity=3)
    yield arabic_agent
    reset_for_tests()


def off_loop(fn, *args, **kwargs):
    """Run a service call on a plain thread.

    Playwright's sync API drives the browser from a thread that owns a running event loop, and
    anything reaching `async_to_sync` from there raises. Every broadcast in this product goes
    through it, so a test that calls a messaging service directly has to step outside first.
    """
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(fn, *args, **kwargs).result(timeout=30)


def _sign_in(page, server, user, password="rtl-test-password"):
    page.goto(f"{server.url}/sign-in/")
    page.fill("input[name='email']", user.email)
    page.fill("input[name='password']", password)
    page.click("button[type='submit']")
    page.wait_for_load_state("networkidle")
    return page


def _start_chat(page, server, category):
    page.goto(f"{server.url}/chat/widget/")
    page.fill("input[name='full_name']", "سارة أحمد")
    page.fill("input[name='email']", "sara@najd.example")
    page.fill("input[name='subject']", "لم يصل الشحن")
    page.select_option("select[name='category']", str(category.pk))
    page.click("button[type='submit']")
    page.wait_for_selector("#chat-thread", timeout=10000)
    return page


def test_a_whole_conversation_between_two_browsers(
    browser, asgi_live_server, desk_open, rtl_fixtures
):
    """The customer speaks; the agent reads it on the conversation they were assigned.

    The console lists conversations rather than rendering their messages — the unread badge is
    what changes there — so the agent's reading happens on the conversation view, which is
    where an agent actually works.
    """
    from apps.chat.models import Conversation

    visitor = browser.new_page()
    agent_page = browser.new_page()
    try:
        _start_chat(visitor, asgi_live_server, rtl_fixtures["category"])
        visitor.fill(".chat-composer textarea", "لم يصل الشحن رغم تسجيله كمُسلَّم")
        visitor.click(".chat-composer button[type='submit']")
        visitor.wait_for_selector("text=لم يصل الشحن رغم تسجيله", timeout=10000)

        conversation = Conversation.objects.order_by("-pk").first()
        assert (
            conversation.assigned_to_id == desk_open.pk
        ), "the visitor was queued rather than connected; the desk fixture is not online"

        _sign_in(agent_page, asgi_live_server, desk_open)
        agent_page.goto(f"{asgi_live_server.url}/chat/conversations/{conversation.pk}/")
        agent_page.wait_for_load_state("networkidle")

        assert "لم يصل الشحن رغم تسجيله" in agent_page.inner_text("#chat-thread")
    finally:
        visitor.close()
        agent_page.close()


def test_the_console_lists_the_new_conversation(browser, asgi_live_server, desk_open, rtl_fixtures):
    """What the console is actually for: the agent sees that a customer is waiting on them."""
    visitor = browser.new_page()
    agent_page = browser.new_page()
    try:
        _start_chat(visitor, asgi_live_server, rtl_fixtures["category"])

        _sign_in(agent_page, asgi_live_server, desk_open)
        agent_page.goto(f"{asgi_live_server.url}/chat/console/")
        agent_page.wait_for_load_state("networkidle")

        assert "سارة أحمد" in agent_page.inner_text("body")
    finally:
        visitor.close()
        agent_page.close()


def test_the_customer_sees_the_agents_reply(browser, asgi_live_server, desk_open, rtl_fixtures):
    """The other direction, which is the half a one-sided test always gets wrong."""
    from apps.chat.models import Conversation
    from apps.chat.services import messaging

    visitor = browser.new_page()
    try:
        _start_chat(visitor, asgi_live_server, rtl_fixtures["category"])
        visitor.fill(".chat-composer textarea", "سؤال")
        visitor.click(".chat-composer button[type='submit']")
        visitor.wait_for_selector("text=سؤال", timeout=10000)

        conversation = Conversation.objects.order_by("-pk").first()
        off_loop(messaging.agent_message, conversation, desk_open, "سنتحقق من الشحنة الآن")

        visitor.wait_for_selector("text=سنتحقق من الشحنة الآن", timeout=10000)
        assert "سنتحقق من الشحنة الآن" in visitor.inner_text("#chat-thread")
    finally:
        visitor.close()


def test_a_private_note_never_appears_in_the_customers_browser(
    browser, asgi_live_server, desk_open, rtl_fixtures
):
    """The whole feature's worst failure, checked where it would actually happen: on the
    customer's screen, in a real browser, with a real socket open."""
    from apps.chat.models import Conversation
    from apps.chat.services import messaging

    visitor = browser.new_page()
    try:
        _start_chat(visitor, asgi_live_server, rtl_fixtures["category"])
        visitor.fill(".chat-composer textarea", "سؤال")
        visitor.click(".chat-composer button[type='submit']")
        visitor.wait_for_selector("text=سؤال", timeout=10000)

        conversation = Conversation.objects.order_by("-pk").first()
        off_loop(messaging.whisper, conversation, desk_open, "لا تَعِد باسترداد المبلغ")
        off_loop(messaging.agent_message, conversation, desk_open, "سنتحقق الآن")

        # Wait for the public message that was sent AFTER the note: if the note were going to
        # arrive, it would have arrived first.
        visitor.wait_for_selector("text=سنتحقق الآن", timeout=10000)

        body = visitor.inner_text("body")
        assert "لا تَعِد باسترداد المبلغ" not in body
        assert "لا يراها العميل" not in body
    finally:
        visitor.close()
