from django.core.management.base import BaseCommand

from accountssu.models import User
from chatsu.choices import MessageRole
from chatsu.models import ChatMessage, ChatSession
from knowledgesu.choices import DocStatus, DocType
from knowledgesu.models import KnowledgeDocument
from ticketssu.choices import (
    TicketActivityType,
    TicketCategory,
    TicketPriority,
    TicketStatus,
)
from ticketssu.models import SLAPolicy, Ticket, TicketActivity, TicketMessage


class Command(BaseCommand):
    help = "Seed demo data matching frontend mock data"

    def handle(self, *args, **options):
        if User.objects.filter(email="admin@company.com").exists():
            self.stdout.write(self.style.WARNING("Data already seeded. Skipping."))
            return

        admin = User.objects.create_user(
            username="admin@company.com", email="admin@company.com",
            password="demo1234", first_name="Admin", last_name="User", role="admin",
        )
        rahim = User.objects.create_user(
            username="rahim@example.com", email="rahim@example.com",
            password="demo1234", first_name="Rahim", last_name="Ahmed", role="customer",
        )
        karim = User.objects.create_user(
            username="karim@example.com", email="karim@example.com",
            password="demo1234", first_name="Karim", last_name="Hassan", role="customer",
        )
        sara = User.objects.create_user(
            username="sara@company.com", email="sara@company.com",
            password="demo1234", first_name="Sara", last_name="Khan", role="agent",
            max_open_tickets=10, is_available=False,
        )
        jamal = User.objects.create_user(
            username="jamal@company.com", email="jamal@company.com",
            password="demo1234", first_name="Jamal", last_name="Uddin", role="agent",
            max_open_tickets=10, is_available=False,
        )

        for priority, fr, res in [
            ("urgent", 1, 4), ("high", 4, 24), ("medium", 8, 48), ("low", 24, 72),
        ]:
            SLAPolicy.objects.create(
                priority=priority, first_response_hours=fr,
                resolution_hours=res, is_active=True,
            )

        tickets_data = [
            ("T-1001", rahim, None, "Cannot reset my password",
             "I tried resetting my password but the email never arrives.", "open", "high", "account"),
            ("T-1002", karim, sara, "Billing charged twice this month",
             "My credit card was charged $49.99 twice on June 5th.", "in_progress", "urgent", "billing"),
            ("T-1003", rahim, jamal, "API returns 500 error on /users endpoint",
             "GET /api/v1/users returns 500 Internal Server Error.", "in_progress", "high", "technical"),
            ("T-1004", karim, sara, "How to upgrade my plan?",
             "I want to upgrade from Basic to Pro plan.", "resolved", "low", "general"),
            ("T-1005", rahim, None, "Two-factor authentication not working",
             "Authenticator app codes are rejected.", "open", "medium", "account"),
        ]

        for uid, customer, agent, subject, desc, status, priority, category in tickets_data:
            ticket = Ticket(
                ticket_uid=uid, customer=customer, assigned_agent=agent,
                subject=subject, description=desc, status=status,
                priority=priority, category=category,
                ai_classification={"category": category, "priority": priority, "sentiment": "neutral"},
            )
            ticket.save()
            TicketActivity.objects.create(
                ticket=ticket, activity_type=TicketActivityType.CREATED,
                message="Ticket submitted successfully", actor=customer,
            )
            TicketActivity.objects.create(
                ticket=ticket, activity_type=TicketActivityType.AI_CLASSIFIED,
                message=f"AI classified as {category.title()} · {priority.title()} priority",
            )
            if agent:
                TicketActivity.objects.create(
                    ticket=ticket, activity_type=TicketActivityType.AGENT_ASSIGNED,
                    message=f"{agent.get_full_name()} accepted your ticket", actor=agent,
                )

        t2 = Ticket.objects.get(ticket_uid="T-1002")
        TicketMessage.objects.create(
            ticket=t2, sender=sara, is_internal=False,
            content="I can see the duplicate charge. Processing refund now.",
        )
        t3 = Ticket.objects.get(ticket_uid="T-1003")
        TicketMessage.objects.create(
            ticket=t3, sender=jamal, is_internal=False,
            content="Root cause found — database connection pool exhausted. Deploying fix.",
        )

        KnowledgeDocument.objects.create(
            title="Refund Policy", doc_type=DocType.PDF, status=DocStatus.READY,
            uploaded_by=admin, metadata={"page_count": 12},
        )
        KnowledgeDocument.objects.create(
            title="FAQ - Billing", doc_type=DocType.FAQ, status=DocStatus.READY, uploaded_by=admin,
        )
        KnowledgeDocument.objects.create(
            title="API Documentation v2", doc_type=DocType.PDF, status=DocStatus.READY,
            uploaded_by=admin, metadata={"page_count": 85},
        )

        session = ChatSession.objects.create(customer=rahim, is_ai_handled=True)
        ChatMessage.objects.create(session=session, role=MessageRole.USER, content="What is your refund policy?")
        ChatMessage.objects.create(
            session=session, role=MessageRole.ASSISTANT,
            content="You can request a full refund within 30 days of purchase.",
            sources=[{"title": "Refund Policy.pdf", "snippet": "Customers may request a full refund within 30 days..."}],
        )

        self.stdout.write(self.style.SUCCESS("Demo data seeded successfully!"))
        self.stdout.write("Login: rahim@example.com / demo1234 (customer)")
        self.stdout.write("Login: sara@company.com / demo1234 (agent)")
        self.stdout.write("Login: admin@company.com / demo1234 (admin)")
