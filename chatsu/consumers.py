from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.layers import get_channel_layer
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone

from chatsu.choices import MessageRole
from chatsu.models import ChatMessage, ChatSession
from meapi.serializers.chat import ChatMessageSerializer


def chat_group_name(session_id: int) -> str:
    return f"chat_session_{session_id}"


def broadcast_chat_event(session_id: int, event_type: str, payload: dict) -> None:
    """Sync helper so REST views can push events to connected sockets."""
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        chat_group_name(session_id),
        {"type": "chat.event", "event_type": event_type, "payload": payload},
    )


class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.session_id = int(self.scope["url_route"]["kwargs"]["session_id"])
        self.group_name = chat_group_name(self.session_id)
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
                "type": "chat.ready",
                "payload": {"session_id": self.session_id, "user_id": user.id, "role": user.role},
            }
        )

    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        event_type = content.get("type")
        payload = content.get("payload") or {}
        user = self.scope["user"]

        if event_type == "chat.message":
            await self._handle_message(user, payload)
        elif event_type == "chat.typing":
            await self._handle_typing(user, payload)
        elif event_type == "chat.seen":
            await self._handle_seen(user, payload)
        else:
            await self.send_json({"type": "chat.error", "payload": {"detail": "Unknown event type"}})

    async def chat_event(self, event):
        await self.send_json({"type": event["event_type"], "payload": event["payload"]})

    async def _handle_message(self, user, payload):
        text = (payload.get("content") or "").strip()
        if not text:
            await self.send_json({"type": "chat.error", "payload": {"detail": "Message cannot be empty"}})
            return

        message = await self._create_message(user, text)
        if message is None:
            await self.send_json(
                {"type": "chat.error", "payload": {"detail": "Cannot send: session not escalated or forbidden"}}
            )
            return

        data = await self._serialize_message(message)
        await self.channel_layer.group_send(
            self.group_name,
            {"type": "chat.event", "event_type": "chat.message", "payload": {"message": data}},
        )

    async def _handle_typing(self, user, payload):
        is_typing = bool(payload.get("is_typing"))
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "chat.event",
                "event_type": "chat.typing",
                "payload": {
                    "user_id": user.id,
                    "role": user.role,
                    "name": user.get_full_name() or user.email,
                    "is_typing": is_typing,
                },
            },
        )

    async def _handle_seen(self, user, payload):
        result = await self._mark_seen(user)
        if result is None:
            return
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "chat.event",
                "event_type": "chat.seen",
                "payload": result,
            },
        )

    @database_sync_to_async
    def _user_can_access(self, user_id: int) -> bool:
        try:
            session = ChatSession.objects.select_related("customer", "escalated_to_agent").get(pk=self.session_id)
        except ChatSession.DoesNotExist:
            return False
        from accountssu.models import User

        user = User.objects.get(pk=user_id)
        if user.role == "admin":
            return True
        if user.role == "customer":
            return session.customer_id == user.id
        if user.role == "agent":
            # Any agent can join live/escalated rooms
            return not session.is_ai_handled
        return False

    @database_sync_to_async
    def _create_message(self, user, content: str):
        try:
            session = ChatSession.objects.get(pk=self.session_id)
        except ChatSession.DoesNotExist:
            return None

        if session.is_ai_handled:
            # Live agent WS is only for escalated chats; AI path stays on REST.
            return None

        if user.role == "customer" and session.customer_id != user.id:
            return None
        # After human handoff, customers continue on the ticket — not live chat WS
        if user.role == "customer":
            return None
        if user.role == "agent" and session.escalated_to_agent_id is None:
            session.escalated_to_agent = user
            session.save(update_fields=["escalated_to_agent", "updated_at"])

        role = MessageRole.USER if user.role == "customer" else MessageRole.AGENT
        message = ChatMessage.objects.create(session=session, role=role, content=content)
        from chatsu.services import mirror_chat_message_to_ticket
        from notificationssu.services import notify_ticket_reply

        ticket_msg = mirror_chat_message_to_ticket(message)
        if ticket_msg is not None and session.ticket_id:
            notify_ticket_reply(
                ticket=session.ticket,
                sender=user,
                content=content,
                is_internal=False,
            )
        return message

    @database_sync_to_async
    def _serialize_message(self, message: ChatMessage) -> dict:
        return ChatMessageSerializer(message).data

    @database_sync_to_async
    def _mark_seen(self, user) -> dict | None:
        try:
            session = ChatSession.objects.get(pk=self.session_id)
        except ChatSession.DoesNotExist:
            return None

        if user.role == "customer":
            qs = session.messages.filter(role=MessageRole.AGENT, seen_at__isnull=True)
        elif user.role == "agent":
            qs = session.messages.filter(role=MessageRole.USER, seen_at__isnull=True)
        else:
            return None

        now = timezone.now()
        ids = list(qs.values_list("id", flat=True))
        if not ids:
            return {"message_ids": [], "seen_at": now.isoformat(), "reader_id": user.id, "reader_role": user.role}

        qs.update(seen_at=now)
        return {
            "message_ids": ids,
            "seen_at": now.isoformat(),
            "reader_id": user.id,
            "reader_role": user.role,
        }
