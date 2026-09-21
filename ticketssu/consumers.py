from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.layers import get_channel_layer
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone

from meapi.serializers.ticket import TicketMessageSerializer
from ticketssu.access import user_can_access_ticket
from ticketssu.choices import TicketStatus
from ticketssu.models import Ticket, TicketMessage


def ticket_group_name(ticket_uid: str) -> str:
    return f"ticket_{ticket_uid}"


AGENT_QUEUE_GROUP = "agent_ticket_queue"


def broadcast_ticket_event(ticket_uid: str, event_type: str, payload: dict) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        ticket_group_name(ticket_uid),
        {"type": "ticket.event", "event_type": event_type, "payload": payload},
    )


def broadcast_agent_queue_event(event_type: str, payload: dict) -> None:
    """Push ticket list changes to all connected agents/admins."""
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        AGENT_QUEUE_GROUP,
        {"type": "queue.event", "event_type": event_type, "payload": payload},
    )


class AgentQueueConsumer(AsyncJsonWebsocketConsumer):
    """Live agent ticket queue — receives ticket.created / ticket.updated."""

    async def connect(self):
        user = self.scope.get("user")
        if user is None or isinstance(user, AnonymousUser) or not user.is_authenticated:
            await self.close(code=4401)
            return
        if getattr(user, "role", None) not in ("agent", "admin"):
            await self.close(code=4403)
            return

        self.group_name = AGENT_QUEUE_GROUP
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json(
            {
                "type": "queue.ready",
                "payload": {"user_id": user.id, "role": user.role},
            }
        )

    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def queue_event(self, event):
        await self.send_json({"type": event["event_type"], "payload": event["payload"]})


class TicketConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.ticket_uid = self.scope["url_route"]["kwargs"]["ticket_uid"]
        self.group_name = ticket_group_name(self.ticket_uid)
        user = self.scope.get("user")

        if user is None or isinstance(user, AnonymousUser) or not user.is_authenticated:
            await self.close(code=4401)
            return

        allowed = await self._user_can_access(user.id)
        if not allowed:
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json(
            {
                "type": "ticket.ready",
                "payload": {
                    "ticket_uid": self.ticket_uid,
                    "user_id": user.id,
                    "role": user.role,
                },
            }
        )

    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        event_type = content.get("type")
        payload = content.get("payload") or {}
        user = self.scope["user"]

        if event_type == "ticket.message":
            await self._handle_message(user, payload)
        elif event_type == "ticket.typing":
            await self._handle_typing(user, payload)
        elif event_type == "ticket.seen":
            await self._handle_seen(user)
        else:
            await self.send_json({"type": "ticket.error", "payload": {"detail": "Unknown event type"}})

    async def ticket_event(self, event):
        await self.send_json({"type": event["event_type"], "payload": event["payload"]})

    async def _handle_message(self, user, payload):
        text = (payload.get("content") or "").strip()
        if not text:
            await self.send_json({"type": "ticket.error", "payload": {"detail": "Message cannot be empty"}})
            return

        result = await self._create_message(user, text, bool(payload.get("is_internal")))
        if result is None:
            await self.send_json({"type": "ticket.error", "payload": {"detail": "Forbidden or ticket not found"}})
            return
        if isinstance(result, dict) and result.get("error"):
            await self.send_json({"type": "ticket.error", "payload": {"detail": result["error"]}})
            return

        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "ticket.event",
                "event_type": "ticket.message",
                "payload": {"message": result},
            },
        )

    async def _handle_typing(self, user, payload):
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "ticket.event",
                "event_type": "ticket.typing",
                "payload": {
                    "user_id": user.id,
                    "role": user.role,
                    "name": user.get_full_name() or user.email,
                    "is_typing": bool(payload.get("is_typing")),
                },
            },
        )

    async def _handle_seen(self, user):
        result = await self._mark_seen(user)
        if result is None:
            return
        await self.channel_layer.group_send(
            self.group_name,
            {"type": "ticket.event", "event_type": "ticket.seen", "payload": result},
        )

    @database_sync_to_async
    def _user_can_access(self, user_id: int) -> bool:
        from accountssu.models import User

        try:
            ticket = Ticket.objects.get(ticket_uid=self.ticket_uid)
            user = User.objects.get(pk=user_id)
        except (Ticket.DoesNotExist, User.DoesNotExist):
            return False
        return user_can_access_ticket(user, ticket)

    @database_sync_to_async
    def _create_message(self, user, content: str, is_internal: bool):
        try:
            ticket = Ticket.objects.get(ticket_uid=self.ticket_uid)
        except Ticket.DoesNotExist:
            return None
        if not user_can_access_ticket(user, ticket):
            return None
        if ticket.status in (TicketStatus.RESOLVED, TicketStatus.CLOSED):
            return {"error": "Ticket is resolved — replies are closed"}

        internal = bool(is_internal) and user.role in ("agent", "admin")
        if user.role == "customer":
            internal = False

        message = TicketMessage.objects.create(
            ticket=ticket,
            sender=user,
            content=content,
            is_internal=internal,
        )

        if not ticket.first_response_at and user.role in ("agent", "admin"):
            ticket.first_response_at = timezone.now()
            ticket.status = TicketStatus.IN_PROGRESS
            ticket.save(update_fields=["first_response_at", "status", "updated_at"])

        from notificationssu.services import notify_ticket_reply
        from chatsu.services import mirror_ticket_message_to_chat

        notify_ticket_reply(
            ticket=ticket,
            sender=user,
            content=content,
            is_internal=internal,
        )
        mirror_ticket_message_to_chat(message)
        return TicketMessageSerializer(message).data

    @database_sync_to_async
    def _mark_seen(self, user) -> dict | None:
        try:
            ticket = Ticket.objects.get(ticket_uid=self.ticket_uid)
        except Ticket.DoesNotExist:
            return None
        if not user_can_access_ticket(user, ticket):
            return None

        qs = TicketMessage.objects.filter(ticket=ticket, seen_at__isnull=True).exclude(sender=user)
        if user.role == "customer":
            qs = qs.filter(is_internal=False)

        now = timezone.now()
        ids = list(qs.values_list("id", flat=True))
        if ids:
            qs.update(seen_at=now)
        return {
            "message_ids": ids,
            "seen_at": now.isoformat(),
            "reader_id": user.id,
            "reader_role": user.role,
        }
