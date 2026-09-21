from django.conf import settings
from django.db import models

from chatsu.choices import MessageRole
from common.models import BaseModel


class ChatSession(BaseModel):
    chat_uid = models.CharField(max_length=20, unique=True, editable=False, blank=True)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_sessions"
    )
    ticket = models.ForeignKey(
        "ticketssu.Ticket", on_delete=models.SET_NULL, null=True, blank=True, related_name="chat_sessions"
    )
    is_ai_handled = models.BooleanField(default=True)
    escalated_to_agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="escalated_chats",
    )

    class Meta:
        db_table = "chat_sessions"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.chat_uid or self.id} - {self.customer.username}"

    def save(self, *args, **kwargs):
        if not self.chat_uid:
            last = ChatSession.objects.exclude(chat_uid="").order_by("-id").first()
            if last and last.chat_uid and "-" in last.chat_uid:
                try:
                    next_num = int(last.chat_uid.split("-")[1]) + 1
                except ValueError:
                    next_num = 1001
            else:
                next_num = 1001
            self.chat_uid = f"C-{next_num}"
        super().save(*args, **kwargs)


class ChatMessage(BaseModel):
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=20, choices=MessageRole.choices)
    content = models.TextField()
    sources = models.JSONField(null=True, blank=True)
    seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "chat_messages"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.role}: {self.content[:50]}"
