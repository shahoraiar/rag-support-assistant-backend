from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsAgentOrAdmin, IsCustomer
from meapi.serializers.ticket import (
    TicketActivitySerializer,
    TicketCreateSerializer,
    TicketMessageSerializer,
    TicketSerializer,
)
from notificationssu.services import notify_ticket_assigned, notify_ticket_reply
from ticketssu.access import tickets_for_user, user_can_access_ticket
from ticketssu.choices import TicketActivityType, TicketStatus
from ticketssu.consumers import broadcast_agent_queue_event, broadcast_ticket_event
from ticketssu.models import Ticket, TicketActivity, TicketMessage


class TicketListCreateView(generics.ListCreateAPIView):
    @extend_schema(tags=["Tickets"], summary="List tickets for current user role")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(tags=["Tickets"], summary="Create a new ticket (customer only)", responses=TicketSerializer)
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def get_serializer_class(self):
        if self.request.method == "POST":
            return TicketCreateSerializer
        return TicketSerializer

    def get_queryset(self):
        return tickets_for_user(self.request.user)

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsCustomer()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(
            TicketSerializer(serializer.instance).data,
            status=status.HTTP_201_CREATED,
        )

    def perform_create(self, serializer):
        serializer.save()


class TicketDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = TicketSerializer
    lookup_field = "ticket_uid"
    lookup_url_kwarg = "ticket_uid"

    def get_queryset(self):
        return tickets_for_user(self.request.user)


class TicketCommentView(APIView):
    def get(self, request, ticket_uid):
        try:
            ticket = Ticket.objects.get(ticket_uid=ticket_uid)
        except Ticket.DoesNotExist:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

        if not user_can_access_ticket(request.user, ticket):
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        messages = TicketMessage.objects.filter(ticket=ticket).select_related("sender").order_by("created_at")
        if request.user.role == "customer":
            messages = messages.filter(is_internal=False)
        return Response(TicketMessageSerializer(messages, many=True).data)

    def post(self, request, ticket_uid):
        try:
            ticket = Ticket.objects.get(ticket_uid=ticket_uid)
        except Ticket.DoesNotExist:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

        is_internal = request.data.get("is_internal", False) and request.user.role in ("agent", "admin")
        if not user_can_access_ticket(request.user, ticket):
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
        if ticket.status in (TicketStatus.RESOLVED, TicketStatus.CLOSED):
            return Response(
                {"detail": "Ticket is resolved — replies are closed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        message = TicketMessage.objects.create(
            ticket=ticket,
            sender=request.user,
            content=request.data.get("content", ""),
            is_internal=is_internal,
        )
        if not ticket.first_response_at and request.user.role in ("agent", "admin"):
            ticket.first_response_at = timezone.now()
            ticket.status = TicketStatus.IN_PROGRESS
            ticket.save(update_fields=["first_response_at", "status", "updated_at"])

        data = TicketMessageSerializer(message).data
        if not (is_internal and request.user.role in ("agent", "admin")):
            broadcast_ticket_event(ticket.ticket_uid, "ticket.message", {"message": data})
        elif request.user.role in ("agent", "admin"):
            # Internal notes still push to agents in the room
            broadcast_ticket_event(ticket.ticket_uid, "ticket.message", {"message": data})
        notify_ticket_reply(
            ticket=ticket,
            sender=request.user,
            content=message.content,
            is_internal=is_internal,
        )
        from chatsu.services import mirror_ticket_message_to_chat

        mirror_ticket_message_to_chat(message)
        return Response(data, status=status.HTTP_201_CREATED)


class TicketAssignView(APIView):
    permission_classes = [IsAgentOrAdmin]

    def post(self, request, ticket_uid):
        try:
            ticket = Ticket.objects.get(ticket_uid=ticket_uid)
        except Ticket.DoesNotExist:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

        agent_id = request.data.get("agent_id", request.user.id)
        from accountssu.models import User
        agent = User.objects.get(id=agent_id, role="agent")
        ticket.assigned_agent = agent
        ticket.status = TicketStatus.IN_PROGRESS
        ticket.save(update_fields=["assigned_agent", "status", "updated_at"])
        TicketActivity.objects.create(
            ticket=ticket,
            activity_type=TicketActivityType.AGENT_ASSIGNED,
            message=f"{agent.get_full_name()} accepted your ticket",
            actor=agent,
        )
        notify_ticket_assigned(ticket=ticket, agent=agent)
        data = TicketSerializer(ticket).data
        broadcast_ticket_event(ticket.ticket_uid, "ticket.updated", {"ticket": data})
        broadcast_agent_queue_event("ticket.updated", {"ticket": data})
        return Response(data)


class TicketResolveView(APIView):
    permission_classes = [IsAgentOrAdmin]

    def post(self, request, ticket_uid):
        try:
            ticket = Ticket.objects.get(ticket_uid=ticket_uid)
        except Ticket.DoesNotExist:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

        if ticket.status in (TicketStatus.RESOLVED, TicketStatus.CLOSED):
            return Response(TicketSerializer(ticket).data)

        ticket.status = TicketStatus.RESOLVED
        ticket.resolved_at = timezone.now()
        ticket.save(update_fields=["status", "resolved_at", "updated_at"])
        TicketActivity.objects.create(
            ticket=ticket,
            activity_type=TicketActivityType.RESOLVED,
            message="Ticket marked as resolved",
            actor=request.user,
        )
        data = TicketSerializer(ticket).data
        broadcast_ticket_event(ticket.ticket_uid, "ticket.updated", {"ticket": data})
        broadcast_agent_queue_event("ticket.updated", {"ticket": data})
        return Response(data)


class TicketActivityListView(generics.ListAPIView):
    serializer_class = TicketActivitySerializer

    def get_queryset(self):
        return TicketActivity.objects.filter(
            ticket__ticket_uid=self.kwargs["ticket_uid"]
        ).select_related("actor")
