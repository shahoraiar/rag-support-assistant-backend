from django.urls import path

from chatsu.consumers import ChatConsumer
from notificationssu.consumers import NotificationConsumer
from ticketssu.consumers import AgentQueueConsumer, TicketConsumer

websocket_urlpatterns = [
    path("ws/chat/<int:session_id>/", ChatConsumer.as_asgi()),
    path("ws/tickets/queue/", AgentQueueConsumer.as_asgi()),
    path("ws/tickets/<str:ticket_uid>/", TicketConsumer.as_asgi()),
    path("ws/notifications/", NotificationConsumer.as_asgi()),
]
