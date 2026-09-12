"""
ASGI entry point (ADR-007).

One application serves both protocols: ordinary HTTP goes to Django unchanged, WebSocket goes
to Channels. Every view, template and middleware written before live chat keeps working
exactly as it did — this is a change to how the application is *served*, not to what it does.

Two things about the order below are deliberate:

- `get_asgi_application()` is called before the Channels imports. It populates the app
  registry, and a consumer module that imports a model before that happens fails with
  AppRegistryNotReady — a confusing error a long way from its cause.
- `AllowedHostsOriginValidator` wraps the WebSocket router, not the HTTP one. A browser
  applies the same-origin policy to fetches but **not** to WebSocket connections, so without
  this any site could open a socket against this one and ride the visitor's cookies.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

# Must come first: it readies the app registry that the imports below depend on.
django_asgi_application = get_asgi_application()

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402

from apps.chat.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_application,
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        ),
    }
)
