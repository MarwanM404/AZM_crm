"""
What live chat does when the realtime service is not there.

Reported as "the go online button doesn't work". It did not work, and — much worse — it did not
say so: the socket handshake failed, the button changed nothing, and the only evidence anywhere
was a line in the browser's developer console. An administrator clicking a button that silently
does nothing has no way to tell a broken product from a broken installation.

The cause on the machine that reported it was Redis not running; the channel layer needs it
(ADR-007). But the cause is not the point. A dropped connection, a proxy that does not upgrade
WebSockets, and a Redis outage in production all produce the same dead socket, and the product
must say something in every one of them.

These tests run against the real ASGI server with the Redis channel layer configured and no
Redis listening — exactly the state a developer reaches by running `manage.py runserver` after
`pip install`.
"""

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


@pytest.fixture
def no_realtime(settings):
    """The channel layer local and production actually use, pointed at nothing.

    Not an in-memory layer and not a monkeypatched failure: the test settings use an in-memory
    layer precisely so the rest of the suite need not care, and that is why every existing test
    passes while this is broken.

    The port is allocated rather than hard-coded, and this matters more than it looks. Written
    first as Redis's own 6379, these tests passed on a machine where Redis happened to be
    stopped and failed the moment it started — and CI runs a Redis service, so they would have
    been red there from the first push. The environment was doing the asserting, not the code.

    The assertion below is the guard: if anything answers on the port, the test says so instead
    of reporting a connected socket as a disconnected one.
    """
    import socket

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    try:
        socket.create_connection(("127.0.0.1", port), timeout=0.5).close()
    except OSError:
        pass  # nothing there, which is the point
    else:
        pytest.fail(
            f"something is listening on 127.0.0.1:{port}, so this test would be checking a "
            "working connection against assertions written for a dead one"
        )

    settings.CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [f"redis://127.0.0.1:{port}/0"]},
        }
    }


@pytest.fixture
def signed_in_admin(page, asgi_live_server, db):
    from apps.accounts.models import Branch, Department, User

    department = Department.objects.create(name="Support", name_ar="الدعم")
    branch = Branch.objects.create(name="Head Office", name_ar="المكتب الرئيسي")
    User.objects.create_user(
        email="admin@example.com",
        password="admin-password",
        full_name="Admin",
        role=User.Role.ADMINISTRATOR,
        department=department,
        branch=branch,
        language="en",
    )
    page.goto(f"{asgi_live_server.url}/sign-in/")
    page.fill("input[name='email']", "admin@example.com")
    page.fill("input[name='password']", "admin-password")
    page.click("button[type='submit']")
    page.wait_for_load_state("networkidle")
    return page


def open_console(page, asgi_live_server):
    page.goto(f"{asgi_live_server.url}/chat/console/")
    page.wait_for_load_state("networkidle")
    # The handshake has to be given time to fail. Nothing on the page changes when it does,
    # which is the defect.
    page.wait_for_timeout(2000)
    return page


def test_a_socket_that_dies_after_the_page_loaded_still_reports(signed_in_admin, asgi_live_server):
    """The case the guard inside `toggleOnline` exists for.

    With no realtime service the button is disabled before anyone can press it, so that path
    is unreachable from the page. It is reachable in the situation an agent actually meets:
    the console connects, they work for an hour, the connection drops — a restarted Redis, a
    proxy timeout, a laptop waking from sleep — and the button is live because it was live
    when the page rendered.

    Written after the first version of this test asserted both "clicking it reports" and "it
    is disabled", which cannot both be true of one click.
    """
    page = open_console(signed_in_admin, asgi_live_server)
    assert not page.eval_on_selector(
        ".chat-presence button", "el => el.disabled"
    ), "setup: this test needs a console that connected successfully"

    # The connection drops without the component being told through Alpine.
    page.evaluate("() => { document.querySelector('[x-data]')._x_dataStack[0].socket.close(); }")
    page.wait_for_timeout(500)

    assert "Live chat is not connected" in page.inner_text(
        "body"
    ), "the connection dropped and the console said nothing"


def test_the_console_reports_the_problem_without_being_clicked(
    signed_in_admin, asgi_live_server, no_realtime
):
    """An agent should not have to press a button to discover the desk is not running.

    They may sit on this screen all morning believing they are reachable. The customers
    queueing on the other side are the ones who pay for that.
    """
    page = open_console(signed_in_admin, asgi_live_server)

    assert "Live chat is not connected" in page.inner_text("body")


def test_the_button_is_not_offered_as_if_it_would_work(
    signed_in_admin, asgi_live_server, no_realtime
):
    """A control that cannot do its job should not look ready to do it."""
    page = open_console(signed_in_admin, asgi_live_server)

    disabled = page.eval_on_selector(".chat-presence button", "el => el.disabled")

    assert disabled, "the Go online button is still offered as though pressing it would work"


def test_the_console_works_normally_when_the_socket_opens(signed_in_admin, asgi_live_server):
    """Without the `no_realtime` fixture, so the in-memory test layer is in use and the socket
    connects. Here for the obvious reason: a fix that reports a problem unconditionally would
    pass every test above and break the product for everybody."""
    page = open_console(signed_in_admin, asgi_live_server)

    body = page.inner_text("body")
    assert "Live chat is not connected" not in body
    assert not page.eval_on_selector(".chat-presence button", "el => el.disabled")


# --- the customer's side of the same defect ---


def test_a_customer_is_told_when_their_message_cannot_be_sent(page, asgi_live_server, db):
    """Found while investigating the console, and worse than what was reported.

    `send()` checked that a socket existed and not that it was open. A closed socket is still
    an object, so `.send()` threw `InvalidStateError` inside the Alpine handler: the customer
    pressed Send, their text stayed in the box, and nothing else happened — no reply, no
    error, no indication the message had gone nowhere. They are mid-problem, and the likeliest
    reading of that silence is that support is ignoring them.

    `signalTyping()`, three lines below it, had always checked `readyState`. The guard was
    known; it was missing from the one call that carries the customer's words.

    The socket is stubbed rather than a real conversation started. This is about what happens
    to a message on a dead connection, and building a conversation first would make the test
    fail for reasons that have nothing to do with that.
    """
    # An agent has to be online for the chat UI to render at all — `{% if available %}` gates
    # the whole thing, so without this the composer is not in the DOM and the test times out
    # looking for it.
    from apps.accounts.models import Branch, Department, User
    from apps.chat.services import presence

    department = Department.objects.create(name="Support", name_ar="الدعم")
    branch = Branch.objects.create(name="Head Office", name_ar="المكتب الرئيسي")
    agent = User.objects.create_user(
        email="agent@example.com",
        password="agent-password",
        full_name="Agent",
        role=User.Role.AGENT,
        department=department,
        branch=branch,
    )
    presence.go_online(agent.pk, capacity=3)

    page.goto(f"{asgi_live_server.url}/chat/widget/")
    page.wait_for_load_state("networkidle")

    page.evaluate(
        """() => {
            const c = document.querySelector('[x-data]')._x_dataStack[0];
            c.stage = 'chatting';
            c.socket = { readyState: 3, send() { throw new Error('closed'); } };
        }"""
    )
    page.wait_for_timeout(200)

    composer = ".chat-composer textarea, .chat-composer input[type=text]"
    page.fill(composer, "Is anyone there?")
    page.click(".chat-composer button[type=submit]")
    page.wait_for_timeout(300)

    assert (
        "lost connection" in page.inner_text("body").lower()
    ), "the customer's message could not be sent and the page said nothing"
    assert (
        page.eval_on_selector(composer, "el => el.value") == "Is anyone there?"
    ), "what the customer wrote was lost"


def test_clicking_in_the_moment_before_onclose_fires_still_reports(
    signed_in_admin, asgi_live_server
):
    """The window the guard inside `toggleOnline` exists for, and which nothing reached.

    Added after a mutation: reverting that guard to a bare `return` left every other test in
    this file green. With no realtime service the button is disabled before anyone can press
    it, and the dropped-connection test above closes the socket so `onclose` fires and reports
    for it — so the guard was correct, defensive, and completely uncovered.

    The window is real rather than theoretical. `readyState` becomes CLOSING and then CLOSED
    before `onclose` is dispatched, so a click landing in between finds an enabled button and
    a socket that cannot carry the frame. Simulated here by swapping in a closed socket
    without firing the event, which is what that interval looks like from the component's
    side.
    """
    page = open_console(signed_in_admin, asgi_live_server)
    assert not page.eval_on_selector(
        ".chat-presence button", "el => el.disabled"
    ), "setup: this test needs a console that connected successfully"

    page.evaluate(
        """() => {
            const c = document.querySelector('[x-data]')._x_dataStack[0];
            // readyState 3 is CLOSED. `connected` is left true, which is exactly the state
            // the component is in for the instant before onclose arrives.
            c.socket = { readyState: 3, send() { throw new Error('closed'); } };
        }"""
    )
    page.click(".chat-presence button")
    page.wait_for_timeout(400)

    assert "Live chat is not connected" in page.inner_text(
        "body"
    ), "the button was pressed on a closed socket and silently did nothing"
