from django.conf import settings
from django.db import models

from common.models import BaseModel
from notificationssu.choices import NotificationType


class Notification(BaseModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    notification_type = models.CharField(max_length=30, choices=NotificationType.choices)
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} -> {self.user.username}"
