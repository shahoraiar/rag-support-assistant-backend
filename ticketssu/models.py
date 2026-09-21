from django.conf import settings
from django.db import models

from common.models import BaseModel
from ticketssu.choices import (
    TicketActivityType,
    TicketCategory,
    TicketPriority,
    TicketSource,
    TicketStatus,
)


class SLAPolicy(BaseModel):
    priority = models.CharField(max_length=20, choices=TicketPriority.choices, unique=True)
    first_response_hours = models.PositiveIntegerField()
    resolution_hours = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "sla_policies"
        ordering = ["priority"]

    def __str__(self):
        return f"SLA {self.priority}"


class Ticket(BaseModel):
    ticket_uid = models.CharField(max_length=20, unique=True, editable=False)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="customer_tickets"
    )
    assigned_agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tickets",
    )
    subject = models.CharField(max_length=255)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=TicketStatus.choices, default=TicketStatus.OPEN)
    priority = models.CharField(max_length=20, choices=TicketPriority.choices, default=TicketPriority.MEDIUM)
    category = models.CharField(max_length=20, choices=TicketCategory.choices, default=TicketCategory.GENERAL)
    source = models.CharField(max_length=20, choices=TicketSource.choices, default=TicketSource.WEB)
    sla_due_at = models.DateTimeField(null=True, blank=True)
    first_response_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    ai_classification = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "tickets"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.ticket_uid} - {self.subject}"

    def save(self, *args, **kwargs):
        if not self.ticket_uid:
            last = Ticket.objects.order_by("-id").first()
            next_num = (int(last.ticket_uid.split("-")[1]) + 1) if last and last.ticket_uid else 1001
            self.ticket_uid = f"T-{next_num}"
        super().save(*args, **kwargs)


class TicketMessage(BaseModel):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField()
    is_internal = models.BooleanField(default=False)
    seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "ticket_messages"
        ordering = ["created_at"]

    def __str__(self):
        return f"Message on {self.ticket.ticket_uid}"


class TicketActivity(BaseModel):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="activities")
    activity_type = models.CharField(max_length=30, choices=TicketActivityType.choices)
    message = models.CharField(max_length=500)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        db_table = "ticket_activities"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.ticket.ticket_uid}: {self.activity_type}"
