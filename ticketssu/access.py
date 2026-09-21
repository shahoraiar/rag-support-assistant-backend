from django.db.models import Q

from ticketssu.choices import TicketStatus
from ticketssu.models import Ticket


def tickets_for_user(user):
    qs = Ticket.objects.select_related("customer", "assigned_agent")
    if user.role == "customer":
        return qs.filter(customer=user)
    if user.role == "agent":
        return qs.filter(
            Q(assigned_agent=user)
            | Q(assigned_agent__isnull=True, status=TicketStatus.OPEN)
        )
    return qs


def user_can_access_ticket(user, ticket: Ticket) -> bool:
    if user.role == "admin":
        return True
    if user.role == "customer":
        return ticket.customer_id == user.id
    if user.role == "agent":
        return (
            ticket.assigned_agent_id == user.id
            or (ticket.assigned_agent_id is None and ticket.status == TicketStatus.OPEN)
        )
    return False
