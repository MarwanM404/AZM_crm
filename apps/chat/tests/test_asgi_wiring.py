"""
The ASGI migration itself (T003, T010).

Three properties worth pinning now, before any consumer exists, because each would be
discovered much later and much more confusingly:

1. HTTP still routes to Django. The whole MVP depends on it.
2. A WebSocket from a foreign origin is refused. A browser applies the same-origin policy to
   fetches but **not** to WebSocket connections, so without the validator any site could open
   a socket against this one and ride the visitor's cookies.
3. The app registry is ready before the Channels imports run — the ordering in config/asgi.py
   that produces a confusing AppRegistryNotReady a long way from its cause if reversed.
"""

import pytest
from channels.routing import ProtocolTypeRouter
from channels.security.websocket import OriginValidator
from channels.testing import WebsocketCommunicator

from config.asgi import application


def test_the_asgi_application_serves_both_protocols():
    assert isinstance(application, ProtocolTypeRouter)
    assert "http" in application.application_mapping
    assert "websocket" in application.application_mapping


def test_websocket_traffic_passes_through_origin_validation():
    """Structural for now: removing the validator is a one-line change nothing else notices.

    `AllowedHostsOriginValidator` is a factory function in Channels 4, not a class — it
    returns an `OriginValidator`, which is what this asserts. The behavioural version of this
    test (connect from a foreign origin, be refused) needs a routed consumer to connect to and
    arrives with the visitor socket in Phase 3; it was verified by hand against a live server
    before this migration was written.
    """
    assert isinstance(application.application_mapping["websocket"], OriginValidator), (
        "The WebSocket router is not wrapped in an origin validator. Browsers do not apply "
        "the same-origin policy to WebSocket connections, so any site could open a socket "
        "against this one and ride the visitor's cookies."
    )


@pytest.mark.django_db
async def test_a_socket_on_an_unrouted_path_is_refused_cleanly():
    """No consumers exist yet. An unrouted path must be refused rather than erroring — that is
    the correct behaviour both now and later for a path nobody implemented."""
    communicator = WebsocketCommunicator(application, "/ws/nothing-here/")
    connected, _ = await communicator.connect()
    assert connected is False
    await communicator.disconnect()


def test_the_app_registry_is_ready_when_asgi_is_imported():
    """config/asgi.py calls get_asgi_application() before importing anything from apps.
    Reversing that order fails with AppRegistryNotReady, far from its cause."""
    from django.apps import apps

    assert apps.ready
    assert apps.is_installed("apps.chat")
