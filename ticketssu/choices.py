from django.db import models


class TicketStatus(models.TextChoices):
    OPEN = "open", "Open"
    IN_PROGRESS = "in_progress", "In Progress"
    RESOLVED = "resolved", "Resolved"
    CLOSED = "closed", "Closed"


class TicketPriority(models.TextChoices):
    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"
    URGENT = "urgent", "Urgent"


class TicketCategory(models.TextChoices):
    BILLING = "billing", "Billing"
    TECHNICAL = "technical", "Technical"
    ACCOUNT = "account", "Account"
    GENERAL = "general", "General"


class TicketSource(models.TextChoices):
    WEB = "web", "Web"
    EMAIL = "email", "Email"
    CHAT = "chat", "Chat"


class TicketActivityType(models.TextChoices):
    CREATED = "created", "Created"
    AI_CLASSIFIED = "ai_classified", "AI Classified"
    AGENT_ASSIGNED = "agent_assigned", "Agent Assigned"
    AGENT_REPLIED = "agent_replied", "Agent Replied"
    CUSTOMER_REPLIED = "customer_replied", "Customer Replied"
    RESOLVED = "resolved", "Resolved"
    CHAT_STARTED = "chat_started", "Chat Started"
    CHAT_ESCALATED = "chat_escalated", "Chat Escalated"


class Sentiment(models.TextChoices):
    POSITIVE = "positive", "Positive"
    NEUTRAL = "neutral", "Neutral"
    NEGATIVE = "negative", "Negative"
