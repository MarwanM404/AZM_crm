"""WebSocket routes for live chat (contracts/websocket.md)."""

from django.urls import path

from apps.chat.consumers.agent import AgentConsumer
from apps.chat.consumers.supervisor import SupervisorConsumer
from apps.chat.consumers.visitor import VisitorConsumer

websocket_urlpatterns = [
    path("ws/chat/visitor/", VisitorConsumer.as_asgi()),
    path("ws/chat/agent/", AgentConsumer.as_asgi()),
    path("ws/chat/supervise/", SupervisorConsumer.as_asgi()),
]
