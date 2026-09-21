from rest_framework import serializers

from notificationssu.models import Notification
from ticketssu.models import SLAPolicy


class SLAPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = SLAPolicy
        fields = ("id", "priority", "first_response_hours", "resolution_hours", "is_active")


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ("id", "notification_type", "title", "message", "is_read", "metadata", "created_at")
