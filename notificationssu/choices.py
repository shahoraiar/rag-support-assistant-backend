from django.db import models


class NotificationType(models.TextChoices):
    TICKET_ASSIGNED = "ticket_assigned", "Ticket Assigned"
    NEW_TICKET = "new_ticket", "New Ticket"
    NEW_MESSAGE = "new_message", "New Message"
    SLA_BREACH = "sla_breach", "SLA Breach"
    CHAT_ESCALATED = "chat_escalated", "Chat Escalated"
    DOCUMENT_READY = "document_ready", "Document Ready"
