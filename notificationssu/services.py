from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from meapi.serializers.notification import NotificationSerializer
from notificationssu.choices import NotificationType
from notificationssu.models import Notification


def _broadcast_notification(notification: Notification) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    unread = Notification.objects.filter(user_id=notification.user_id, is_read=False).count()
    async_to_sync(channel_layer.group_send)(
        f"notifications_{notification.user_id}",
        {
            "type": "notification.created",
            "payload": {
                "notification": NotificationSerializer(notification).data,
                "unread_count": unread,
            },
        },
    )


def notify_user(
    *,
    user,
    notification_type: str,
    title: str,
    message: str,
    metadata: dict | None = None,
) -> Notification:
    notification = Notification.objects.create(
        user=user,
        notification_type=notification_type,
        title=title,
        message=message,
        metadata=metadata or {},
    )
    _broadcast_notification(notification)
    return notification


def notify_ticket_reply(*, ticket, sender, content: str, is_internal: bool = False) -> None:
    preview = (content or "").strip()
    if len(preview) > 120:
        preview = preview[:117] + "..."

    if sender.role in ("agent", "admin"):
        if is_internal:
            return
        notify_user(
            user=ticket.customer,
            notification_type=NotificationType.NEW_MESSAGE,
            title=f"Reply on {ticket.ticket_uid}",
            message=f"{sender.get_full_name()}: {preview}",
            metadata={"ticket_uid": ticket.ticket_uid},
        )
        return

    if ticket.assigned_agent_id:
        notify_user(
            user=ticket.assigned_agent,
            notification_type=NotificationType.NEW_MESSAGE,
            title=f"Customer reply on {ticket.ticket_uid}",
            message=f"{sender.get_full_name()}: {preview}",
            metadata={"ticket_uid": ticket.ticket_uid},
        )


def notify_ticket_assigned(*, ticket, agent) -> None:
    notify_user(
        user=agent,
        notification_type=NotificationType.TICKET_ASSIGNED,
        title="Ticket assigned to you",
        message=f"{ticket.ticket_uid}: {ticket.subject}",
        metadata={"ticket_uid": ticket.ticket_uid},
    )
    notify_user(
        user=ticket.customer,
        notification_type=NotificationType.TICKET_ASSIGNED,
        title="Agent assigned",
        message=f"{agent.get_full_name()} is handling {ticket.ticket_uid}",
        metadata={"ticket_uid": ticket.ticket_uid},
    )


def notify_agents_new_ticket(*, ticket) -> None:
    """Push unread notification to online agents when a customer opens a ticket."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    agents = User.objects.filter(role="agent", is_active=True, is_available=True)
    title = "New ticket in queue"
    message = f"{ticket.ticket_uid}: {ticket.subject} ({ticket.priority})"
    metadata = {"ticket_uid": ticket.ticket_uid}
    for agent in agents:
        notify_user(
            user=agent,
            notification_type=NotificationType.NEW_TICKET,
            title=title,
            message=message,
            metadata=metadata,
        )
