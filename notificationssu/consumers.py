from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth.models import AnonymousUser


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    """Per-user notification channel: notifications_{user_id}.

    Agents are marked online while this socket is connected so ticket
    escalation only assigns to agents who are actually in the app.
    """

    async def connect(self):
        user = self.scope.get("user")
        if user is None or isinstance(user, AnonymousUser) or not user.is_authenticated:
            await self.close(code=4401)
            return

        self.user_id = user.id
        self.user_role = getattr(user, "role", None)
        self.group_name = f"notifications_{self.user_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        if self.user_role == "agent":
            await self._set_agent_available(True)

        unread = await self._unread_count()
        await self.send_json(
            {
                "type": "notification.ready",
                "payload": {"user_id": self.user_id, "unread_count": unread},
            }
        )

    async def disconnect(self, code):
        if getattr(self, "user_role", None) == "agent" and getattr(self, "user_id", None):
            await self._set_agent_available(False)
        group = getattr(self, "group_name", None)
        if group:
            await self.channel_layer.group_discard(group, self.channel_name)

    async def notification_created(self, event):
        await self.send_json({"type": "notification.created", "payload": event["payload"]})

    @database_sync_to_async
    def _unread_count(self) -> int:
        from notificationssu.models import Notification

        return Notification.objects.filter(user_id=self.user_id, is_read=False).count()

    @database_sync_to_async
    def _set_agent_available(self, available: bool) -> None:
        from accountssu.models import User

        User.objects.filter(id=self.user_id, role="agent").update(is_available=available)
