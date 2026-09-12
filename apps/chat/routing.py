"""
WebSocket routes for live chat.

Empty until Phase 3 brings the consumers. It exists now so `config/asgi.py` has something
real to point at, and so the ASGI migration can be verified on its own — a socket opened
against this router is refused cleanly rather than erroring, which is the correct behaviour
for a path that has no consumer.
"""

websocket_urlpatterns: list = []
